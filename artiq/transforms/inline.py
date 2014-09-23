from collections import namedtuple, defaultdict
from fractions import Fraction
import inspect
import textwrap
import ast
import builtins

from artiq.transforms.tools import eval_ast, value_to_ast
from artiq.language import core as core_language
from artiq.language import units


_UserVariable = namedtuple("_UserVariable", "name")


def _is_in_attr_list(obj, attr, al):
    if not hasattr(obj, al):
        return False
    return attr in getattr(obj, al).split()


class _ReferenceManager:
    def __init__(self):
        # (id(obj), func_name, local_name) or (id(obj), kernel_attr_name)
        #     -> _UserVariable(name) / ast / constant_object
        self.to_inlined = dict()
        # inlined_name -> use_count
        self.use_count = dict()
        self.rpc_map = defaultdict(lambda: len(self.rpc_map))
        self.exception_map = defaultdict(lambda: len(self.exception_map))
        self.kernel_attr_init = []

        # reserved names
        for kg in core_language.kernel_globals:
            self.use_count[kg] = 1
        for name in ("int", "round", "int64", "round64", "float", "array",
                     "range", "Fraction", "Quantity", "EncodedException",
                     "s_unit", "Hz_unit", "microcycle_unit"):
            self.use_count[name] = 1

    def new_name(self, base_name):
        if base_name[-1].isdigit():
            base_name += "_"
        if base_name in self.use_count:
            r = base_name + str(self.use_count[base_name])
            self.use_count[base_name] += 1
            return r
        else:
            self.use_count[base_name] = 1
            return base_name

    def get(self, obj, func_name, ref):
        if isinstance(ref, ast.Name):
            key = (id(obj), func_name, ref.id)
            try:
                return self.to_inlined[key]
            except KeyError:
                if isinstance(ref.ctx, ast.Store):
                    ival = _UserVariable(self.new_name(ref.id))
                    self.to_inlined[key] = ival
                    return ival
                else:
                    try:
                        return inspect.getmodule(obj).__dict__[ref.id]
                    except KeyError:
                        return getattr(builtins, ref.id)
        elif isinstance(ref, ast.Attribute):
            target = self.get(obj, func_name, ref.value)
            if _is_in_attr_list(target, ref.attr, "kernel_attr"):
                key = (id(target), ref.attr)
                try:
                    ival = self.to_inlined[key]
                    assert(isinstance(ival, _UserVariable))
                except KeyError:
                    iname = self.new_name(ref.attr)
                    ival = _UserVariable(iname)
                    self.to_inlined[key] = ival
                    a = value_to_ast(getattr(target, ref.attr))
                    if a is None:
                        raise NotImplementedError(
                            "Cannot represent initial value"
                            " of kernel attribute")
                    self.kernel_attr_init.append(ast.Assign(
                        [ast.Name(iname, ast.Store())], a))
                return ival
            else:
                return getattr(target, ref.attr)
        else:
            raise NotImplementedError


_embeddable_calls = {
    core_language.delay, core_language.at, core_language.now,
    core_language.syscall,
    range, int, float, round,
    core_language.int64, core_language.round64, core_language.array,
    Fraction, units.Quantity, core_language.EncodedException
}


class _ReferenceReplacer(ast.NodeVisitor):
    def __init__(self, core, rm, obj, func_name, retval_name):
        self.core = core
        self.rm = rm
        self.obj = obj
        self.func_name = func_name
        self.retval_name = retval_name
        self._insertion_point = None

    # This is ast.NodeTransformer.generic_visit from CPython, modified
    # to update self._insertion_point.
    def generic_visit(self, node):
        for field, old_value in ast.iter_fields(node):
            old_value = getattr(node, field, None)
            if isinstance(old_value, list):
                prev_insertion_point = self._insertion_point
                new_values = []
                if field in ("body", "orelse", "finalbody"):
                    self._insertion_point = new_values
                for value in old_value:
                    if isinstance(value, ast.AST):
                        value = self.visit(value)
                        if value is None:
                            continue
                        elif not isinstance(value, ast.AST):
                            new_values.extend(value)
                            continue
                    new_values.append(value)
                old_value[:] = new_values
                self._insertion_point = prev_insertion_point
            elif isinstance(old_value, ast.AST):
                new_node = self.visit(old_value)
                if new_node is None:
                    delattr(node, field)
                else:
                    setattr(node, field, new_node)
        return node

    def visit_ref(self, node):
        store = isinstance(node.ctx, ast.Store)
        ival = self.rm.get(self.obj, self.func_name, node)
        if isinstance(ival, _UserVariable):
            newnode = ast.Name(ival.name, node.ctx)
        elif isinstance(ival, ast.AST):
            assert(not store)
            newnode = ival
        else:
            if store:
                raise NotImplementedError(
                    "Cannot turn object into user variable")
            else:
                newnode = value_to_ast(ival)
                if newnode is None:
                    raise NotImplementedError(
                        "Cannot represent inlined value")
        return ast.copy_location(newnode, node)

    visit_Name = visit_ref
    visit_Attribute = visit_ref

    def visit_Call(self, node):
        func = self.rm.get(self.obj, self.func_name, node.func)
        new_args = [self.visit(arg) for arg in node.args]

        if func in _embeddable_calls:
            new_func = ast.Name(func.__name__, ast.Load())
            return ast.copy_location(
                ast.Call(func=new_func, args=new_args,
                         keywords=[], starargs=None, kwargs=None),
                node)
        elif (hasattr(func, "k_function_info")
              and getattr(func.__self__, func.k_function_info.core_name)
                is self.core):
            retval_name = self.rm.new_name(
                func.k_function_info.k_function.__name__ + "_return")
            args = [func.__self__] + new_args
            inlined, _, _ = inline(self.core, func.k_function_info.k_function,
                                   args, dict(), self.rm, retval_name)
            self._insertion_point.append(ast.With(
                items=[ast.withitem(context_expr=ast.Name(id="sequential",
                                                          ctx=ast.Load()),
                                    optional_vars=None)],
                body=inlined.body))
            return ast.copy_location(ast.Name(retval_name, ast.Load()), node)
        else:
            args = [ast.Str("rpc"), value_to_ast(self.rm.rpc_map[func])]
            args += new_args
            return ast.copy_location(
                ast.Call(func=ast.Name("syscall", ast.Load()),
                         args=args, keywords=[], starargs=None, kwargs=None),
                node)

    def visit_Return(self, node):
        self.generic_visit(node)
        return ast.copy_location(
            ast.Assign(targets=[ast.Name(self.retval_name, ast.Store())],
                       value=node.value),
            node)

    def visit_Expr(self, node):
        self.generic_visit(node)
        if isinstance(node.value, ast.Name):
            # Remove Expr nodes that contain only a name, likely due to
            # function call inlining. Such nodes that were originally in the
            # code are also removed, but this does not affect the semantics of
            # the code as they are nops.
            return None
        else:
            return node

    def visit_FunctionDef(self, node):
        node.args = ast.arguments(args=[], vararg=None, kwonlyargs=[],
                                  kw_defaults=[], kwarg=None, defaults=[])
        node.decorator_list = []
        self.generic_visit(node)
        return node

    def visit_Raise(self, node):
        if node.cause is not None:
            raise NotImplementedError("Exception causes are not supported")
        if node.exc is not None:
            exception_class = self.rm.get(self.obj, self.func_name, node.exc)
            if not inspect.isclass(exception_class):
                raise NotImplementedError("Exception must be a class")
            exception_id = self.rm.exception_map[exception_class]
            node.exc = ast.copy_location(
                    ast.Call(func=ast.Name("EncodedException", ast.Load()),
                             args=[value_to_ast(exception_id)],
                             keywords=[], starargs=None, kwargs=None),
                    node.exc)
        return node

    def _encode_exception(self, e):
        exception_class = self.rm.get(self.obj, self.func_name, e)
        if not inspect.isclass(exception_class):
            raise NotImplementedError("Exception type must be a class")
        exception_id = self.rm.exception_map[exception_class]
        return ast.copy_location(
            ast.Call(func=ast.Name("EncodedException", ast.Load()),
                     args=[value_to_ast(exception_id)],
                     keywords=[], starargs=None, kwargs=None),
            e)

    def visit_ExceptHandler(self, node):
        if node.name is not None:
            raise NotImplementedError("'as target' is not supported")
        if node.type is not None:
            if isinstance(node.type, ast.Tuple):
                node.type.elts = [self._encode_exception(e) for e in node.type.elts]
            else:
                node.type = self._encode_exception(node.type)
        self.generic_visit(node)
        return node


class _ListReadOnlyParams(ast.NodeVisitor):
    def visit_FunctionDef(self, node):
        if hasattr(self, "read_only_params"):
            raise ValueError("More than one function definition")
        self.read_only_params = {arg.arg for arg in node.args.args}
        self.generic_visit(node)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Store):
            try:
                self.read_only_params.remove(node.id)
            except KeyError:
                pass


def _list_read_only_params(func_def):
    lrp = _ListReadOnlyParams()
    lrp.visit(func_def)
    return lrp.read_only_params


def _initialize_function_params(func_def, k_args, k_kwargs, rm):
    obj = k_args[0]
    func_name = func_def.name
    param_init = []
    rop = _list_read_only_params(func_def)
    for arg_ast, arg_value in zip(func_def.args.args, k_args):
        arg_name = arg_ast.arg
        if arg_name in rop:
            rm.to_inlined[(id(obj), func_name, arg_name)] = arg_value
        else:
            target = rm.get(obj, func_name, ast.Name(arg_name, ast.Store()))
            value = value_to_ast(arg_value)
            param_init.append(ast.Assign(targets=[target], value=value))
    return param_init


def inline(core, k_function, k_args, k_kwargs, rm=None, retval_name=None):
    init_kernel_attr = rm is None
    if rm is None:
        rm = _ReferenceManager()

    func_def = ast.parse(textwrap.dedent(inspect.getsource(k_function))).body[0]

    param_init = _initialize_function_params(func_def, k_args, k_kwargs, rm)

    obj = k_args[0]
    func_name = func_def.name
    rr = _ReferenceReplacer(core, rm, obj, func_name, retval_name)
    rr.visit(func_def)

    func_def.body[0:0] = param_init
    if init_kernel_attr:
        func_def.body[0:0] = rm.kernel_attr_init

    r_rpc_map = dict((rpc_num, rpc_fun)
                     for rpc_fun, rpc_num in rm.rpc_map.items())
    r_exception_map = dict((exception_num, exception_class)
                           for exception_class, exception_num
                           in rm.exception_map.items())
    return func_def, r_rpc_map, r_exception_map
