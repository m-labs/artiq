from collections import namedtuple
from fractions import Fraction
import inspect
import textwrap
import ast
import builtins

from artiq.transforms.tools import eval_ast, value_to_ast
from artiq.language import core as core_language
from artiq.language import units


class _HostObjectMapper:
    def __init__(self, first_encoding=0):
        self._next_encoding = first_encoding
        # id(object) -> (encoding, object)
        # this format is required to support non-hashable host objects.
        self._d = dict()

    def encode(self, obj):
        try:
            return self._d[id(obj)][0]
        except KeyError:
            encoding = self._next_encoding
            self._d[id(obj)] = (encoding, obj)
            self._next_encoding += 1
            return encoding

    def get_map(self):
        return {encoding: obj for i, (encoding, obj) in self._d.items()}


_UserVariable = namedtuple("_UserVariable", "name")


def _is_kernel_attr(value, attr):
    return hasattr(value, "kernel_attr") and attr in value.kernel_attr.split()


class _ReferenceManager:
    def __init__(self):
        self.rpc_mapper = _HostObjectMapper()
        self.exception_mapper = _HostObjectMapper(core_language.first_user_eid)
        self.kernel_attr_init = []

        # (id(obj), func_name, ref_name) or (id(obj), kernel_attr_name)
        #     -> _UserVariable(name) / ast / constant_object
        self._to_inlined = dict()
        # inlined_name -> use_count
        self._use_count = dict()
        # reserved names
        for kg in core_language.kernel_globals:
            self._use_count[kg] = 1
        for name in ("bool", "int", "round", "int64", "round64", "float",
                     "Fraction", "array", "Quantity", "EncodedException",
                     "range"):
            self._use_count[name] = 1

    # node_or_value can be a AST node, used to inline function parameter values
    # that can be simplified later through constant folding.
    def register_replace(self, obj, func_name, ref_name, node_or_value):
        self._to_inlined[(id(obj), func_name, ref_name)] = node_or_value

    def new_name(self, base_name):
        if base_name[-1].isdigit():
            base_name += "_"
        if base_name in self._use_count:
            r = base_name + str(self._use_count[base_name])
            self._use_count[base_name] += 1
            return r
        else:
            self._use_count[base_name] = 1
            return base_name

    def resolve_name(self, obj, func_name, ref_name, store):
        key = (id(obj), func_name, ref_name)
        try:
            return self._to_inlined[key]
        except KeyError:
            if store:
                ival = _UserVariable(self.new_name(ref_name))
                self._to_inlined[key] = ival
                return ival
            else:
                try:
                    return inspect.getmodule(obj).__dict__[ref_name]
                except KeyError:
                    return getattr(builtins, ref_name)

    def resolve_attr(self, value, attr):
        if _is_kernel_attr(value, attr):
            key = (id(value), attr)
            try:
                ival = self._to_inlined[key]
                assert(isinstance(ival, _UserVariable))
            except KeyError:
                iname = self.new_name(attr)
                ival = _UserVariable(iname)
                self._to_inlined[key] = ival
                a = value_to_ast(getattr(value, attr))
                if a is None:
                    raise NotImplementedError(
                        "Cannot represent initial value"
                        " of kernel attribute")
                self.kernel_attr_init.append(ast.Assign(
                    [ast.Name(iname, ast.Store())], a))
            return ival
        else:
            return getattr(value, attr)

    def resolve_constant(self, obj, func_name, node):
        if isinstance(node, ast.Name):
            c = self.resolve_name(obj, func_name, node.id, False)
            if isinstance(c, (_UserVariable, ast.AST)):
                raise ValueError("Not a constant")
            return c
        elif isinstance(node, ast.Attribute):
            value = self.resolve_constant(obj, func_name, node.value)
            if _is_kernel_attr(value, node.attr):
                raise ValueError("Not a constant")
            return getattr(value, node.attr)
        else:
            raise NotImplementedError


_embeddable_funcs = (
    core_language.delay, core_language.at, core_language.now,
    core_language.time_to_cycles, core_language.cycles_to_time,
    core_language.syscall,
    range, bool, int, float, round,
    core_language.int64, core_language.round64, core_language.array,
    Fraction, units.Quantity, core_language.EncodedException
)

def _is_embeddable(func):
    for ef in _embeddable_funcs:
        if func is ef:
            return True
    return False


def _is_inlinable(core, func):
    if hasattr(func, "k_function_info"):
        if func.k_function_info.core_name == "":
            return True  # portable function
        if getattr(func.__self__, func.k_function_info.core_name) is core:
            return True  # kernel function for the same core device
    return False


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

    def visit_Name(self, node):
        store = isinstance(node.ctx, ast.Store)
        ival = self.rm.resolve_name(self.obj, self.func_name, node.id, store)
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

    def _resolve_attribute(self, node):
        if isinstance(node, ast.Name):
            ival = self.rm.resolve_name(self.obj, self.func_name, node.id, False)
            if isinstance(ival, _UserVariable):
                return ast.copy_location(ast.Name(ival.name, ast.Load()), node)
            else:
                return ival
        elif isinstance(node, ast.Attribute):
            value = self._resolve_attribute(node.value)
            if isinstance(value, ast.AST):
                node.value = value
                return node
            else:
                return self.rm.resolve_attr(value, node.attr)
        else:
            return self.visit(node)

    def visit_Attribute(self, node):
        ival = self._resolve_attribute(node)
        if isinstance(ival, ast.AST):
            return ival
        elif isinstance(ival, _UserVariable):
            return ast.copy_location(ast.Name(ival.name, node.ctx), node)
        else:
            return value_to_ast(ival)

    def visit_Call(self, node):
        func = self.rm.resolve_constant(self.obj, self.func_name, node.func)
        new_args = [self.visit(arg) for arg in node.args]

        if _is_embeddable(func):
            new_func = ast.Name(func.__name__, ast.Load())
            return ast.copy_location(
                ast.Call(func=new_func, args=new_args,
                         keywords=[], starargs=None, kwargs=None),
                node)
        elif _is_inlinable(self.core, func):
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
            args = [ast.Str("rpc"), value_to_ast(self.rm.rpc_mapper.encode(func))]
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
        if isinstance(node.value, ast.Str):
            # Strip docstrings. This also removes strings appearing in the
            # middle of the code, but they are nops.
            return None
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

    def _encode_exception(self, e):
        exception_class = self.rm.resolve_constant(self.obj, self.func_name, e)
        if not inspect.isclass(exception_class):
            raise NotImplementedError("Exception type must be a class")
        if issubclass(exception_class, core_language.RuntimeException):
            exception_id = exception_class.eid
        else:
            exception_id = self.rm.exception_mapper.encode(exception_class)
        return ast.copy_location(
            ast.Call(func=ast.Name("EncodedException", ast.Load()),
                     args=[value_to_ast(exception_id)],
                     keywords=[], starargs=None, kwargs=None),
            e)

    def visit_Raise(self, node):
        if node.cause is not None:
            raise NotImplementedError("Exception causes are not supported")
        if node.exc is not None:
            node.exc = self._encode_exception(node.exc)
        return node

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
            rm.register_replace(obj, func_name, arg_name, arg_value)
        else:
            uservar = rm.resolve_name(obj, func_name, arg_name, True)
            target = ast.Name(uservar.name, ast.Store())
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

    return func_def, rm.rpc_mapper.get_map(), rm.exception_mapper.get_map()
