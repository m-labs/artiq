import inspect
import textwrap
import ast
import types
import builtins
from copy import copy
from fractions import Fraction
from collections import OrderedDict
from functools import partial
from itertools import zip_longest, chain

from artiq.language import core as core_language
from artiq.language import units
from artiq.transforms.tools import *


def new_mangled_name(in_use_names, name):
    mangled_name = name
    i = 2
    while mangled_name in in_use_names:
        mangled_name = name + str(i)
        i += 1
    in_use_names.add(mangled_name)
    return mangled_name


class MangledName:
    def __init__(self, s):
        self.s = s


class AttributeInfo:
    def __init__(self, obj, mangled_name, read_write):
        self.obj = obj
        self.mangled_name = mangled_name
        self.read_write = read_write


def is_inlinable(core, func):
    if hasattr(func, "k_function_info"):
        if func.k_function_info.core_name == "":
            return True  # portable function
        if getattr(func.__self__, func.k_function_info.core_name) is core:
            return True  # kernel function for the same core device
    return False


class GlobalNamespace:
    def __init__(self, func):
        self.func_gd = inspect.getmodule(func).__dict__

    def __getitem__(self, item):
        try:
            return self.func_gd[item]
        except KeyError:
            return getattr(builtins, item)


class UndefinedArg:
    pass


def get_function_args(func_args, func_tr, args, kwargs):
    # OrderedDict prevents non-determinism in argument init
    r = OrderedDict()

    # Process positional arguments. Any missing positional argument values
    # are set to UndefinedArg.
    for arg, arg_value in zip_longest(func_args.args, args,
                                      fillvalue=UndefinedArg):
        if arg is UndefinedArg:
            raise TypeError("Got too many positional arguments")
        if arg.arg in r:
            raise SyntaxError("Duplicate argument '{}' in function definition"
                              .format(arg.arg))
        r[arg.arg] = arg_value

    # Process keyword arguments. Any missing keyword-only argument values
    # are set to UndefinedArg.
    valid_arg_names = {arg.arg for arg in
                       chain(func_args.args, func_args.kwonlyargs)}
    for arg in func_args.kwonlyargs:
        if arg.arg in r:
            raise SyntaxError("Duplicate argument '{}' in function definition"
                              .format(arg.arg))
        r[arg.arg] = UndefinedArg
    for arg_name, arg_value in kwargs.items():
        if arg_name not in valid_arg_names:
            raise TypeError("Got unexpected keyword argument '{}'"
                            .format(arg_name))
        if r[arg_name] is not UndefinedArg:
            raise TypeError("Got multiple values for argument '{}'"
                            .format(arg_name))
        r[arg_name] = arg_value

    # Replace any UndefinedArg positional arguments with the default value,
    # when provided.
    for arg, default in zip(func_args.args[-len(func_args.defaults):],
                            func_args.defaults):
        if r[arg.arg] is UndefinedArg:
            r[arg.arg] = func_tr.code_visit(default)
    # Same with keyword-only arguments.
    for arg, default in zip(func_args.kwonlyargs, func_args.kw_defaults):
        if default is not None and r[arg.arg] is UndefinedArg:
            r[arg.arg] = func_tr.code_visit(default)

    # Check that no argument was left undefined.
    missing_arguments = ["'"+arg+"'" for arg, value in r.items()
                         if value is UndefinedArg]
    if missing_arguments:
        raise TypeError("Missing argument(s): " + " ".join(missing_arguments))

    return r


# args/kwargs can contain values or AST nodes
def get_inline(core, attribute_namespace, in_use_names, retval_name, mappers,
               func, args, kwargs):
    global_namespace = GlobalNamespace(func)
    func_tr = Function(core,
                       global_namespace, attribute_namespace, in_use_names,
                       retval_name, mappers)
    func_def = ast.parse(textwrap.dedent(inspect.getsource(func))).body[0]

    # Initialize arguments.
    # The local namespace is empty so code_visit will always resolve
    # using the global namespace.
    arg_init = []
    arg_name_map = []
    arg_dict = get_function_args(func_def.args, func_tr, args, kwargs)
    for arg_name, arg_value in arg_dict.items():
        if isinstance(arg_value, ast.AST):
            value = arg_value
        else:
            try:
                value = ast.copy_location(value_to_ast(arg_value), func_def)
            except NotASTRepresentable:
                value = None
        if value is None:
            # static object
            func_tr.local_namespace[arg_name] = arg_value
        else:
            # set parameter value with "name = value"
            # assignment at beginning of function
            new_name = new_mangled_name(in_use_names, arg_name)
            arg_name_map.append((arg_name, new_name))
            target = ast.copy_location(ast.Name(new_name, ast.Store()),
                                       func_def)
            assign = ast.copy_location(ast.Assign([target], value),
                                       func_def)
            arg_init.append(assign)
    # Commit arguments to the local namespace at the end to handle cases
    # such as f(x, y=x) (for the default value of y, x must be resolved
    # using the global namespace).
    for arg_name, mangled_name in arg_name_map:
        func_tr.local_namespace[arg_name] = MangledName(mangled_name)

    func_def = func_tr.code_visit(func_def)
    func_def.body[0:0] = arg_init
    return func_def


class Function:
    def __init__(self, core,
                 global_namespace, attribute_namespace, in_use_names,
                 retval_name, mappers):
        # The core device on which this function is executing.
        self.core = core

        # Local and global namespaces:
        # original name -> MangledName or static object
        self.local_namespace = dict()
        self.global_namespace = global_namespace

        # (id(static object), attribute) -> AttributeInfo
        self.attribute_namespace = attribute_namespace

        # All names currently in use, in the namespace of the combined
        # function.
        # When creating a name for a new object, check that it is not
        # already in this set.
        self.in_use_names = in_use_names

        # Name of the variable to store the return value to, or None
        # to keep the return statement.
        self.retval_name = retval_name

        # Host object mappers, for RPC and exception numbers
        self.mappers = mappers

        self._insertion_point = None

    # This is ast.NodeVisitor/NodeTransformer from CPython, modified
    # to add code_ prefix.
    def code_visit(self, node):
        method = "code_visit_" + node.__class__.__name__
        visitor = getattr(self, method, self.code_generic_visit)
        return visitor(node)

    # This is ast.NodeTransformer.generic_visit from CPython, modified
    # to update self._insertion_point.
    def code_generic_visit(self, node):
        for field, old_value in ast.iter_fields(node):
            old_value = getattr(node, field, None)
            if isinstance(old_value, list):
                prev_insertion_point = self._insertion_point
                new_values = []
                if field in ("body", "orelse", "finalbody"):
                    self._insertion_point = new_values
                for value in old_value:
                    if isinstance(value, ast.AST):
                        value = self.code_visit(value)
                        if value is None:
                            continue
                        elif not isinstance(value, ast.AST):
                            new_values.extend(value)
                            continue
                    new_values.append(value)
                old_value[:] = new_values
                self._insertion_point = prev_insertion_point
            elif isinstance(old_value, ast.AST):
                new_node = self.code_visit(old_value)
                if new_node is None:
                    delattr(node, field)
                else:
                    setattr(node, field, new_node)
        return node

    def code_visit_Name(self, node):
        if isinstance(node.ctx, ast.Store):
            if (node.id in self.local_namespace
                    and isinstance(self.local_namespace[node.id],
                                   MangledName)):
                new_name = self.local_namespace[node.id].s
            else:
                new_name = new_mangled_name(self.in_use_names, node.id)
                self.local_namespace[node.id] = MangledName(new_name)
            node.id = new_name
            return node
        else:
            try:
                obj = self.local_namespace[node.id]
            except KeyError:
                try:
                    obj = self.global_namespace[node.id]
                except KeyError:
                    raise NameError("name '{}' is not defined".format(node.id))
            if isinstance(obj, MangledName):
                node.id = obj.s
                return node
            else:
                try:
                    return value_to_ast(obj)
                except NotASTRepresentable:
                    raise NotImplementedError(
                        "Static object cannot be used here")

    def code_visit_Attribute(self, node):
        # There are two cases of attributes:
        # 1. static object attributes, e.g. self.foo
        # 2. dynamic expression attributes, e.g.
        #    (Fraction(1, 2) + x).numerator
        # Static object resolution has no side effects so we try it first.
        try:
            obj = self.static_visit(node.value)
        except:
            self.code_generic_visit(node)
            return node
        else:
            key = (id(obj), node.attr)
            try:
                attr_info = self.attribute_namespace[key]
            except KeyError:
                new_name = new_mangled_name(self.in_use_names, node.attr)
                attr_info = AttributeInfo(obj, new_name, False)
                self.attribute_namespace[key] = attr_info
            if isinstance(node.ctx, ast.Store):
                attr_info.read_write = True
            return ast.copy_location(
                ast.Name(attr_info.mangled_name, node.ctx),
                node)

    def code_visit_Call(self, node):
        func = self.static_visit(node.func)
        node.args = [self.code_visit(arg) for arg in node.args]
        for kw in node.keywords:
            kw.value = self.code_visit(kw.value)

        if is_embeddable(func):
            node.func = ast.copy_location(
                ast.Name(func.__name__, ast.Load()),
                node)
            return node
        elif is_inlinable(self.core, func):
            retval_name = func.k_function_info.k_function.__name__ + "_return"
            retval_name_m = new_mangled_name(self.in_use_names, retval_name)
            args = [func.__self__] + node.args
            kwargs = {kw.arg: kw.value for kw in node.keywords}
            inlined = get_inline(self.core,
                                 self.attribute_namespace, self.in_use_names,
                                 retval_name_m, self.mappers,
                                 func.k_function_info.k_function,
                                 args, kwargs)
            seq = ast.copy_location(
                ast.With(
                    items=[ast.withitem(context_expr=ast.Name(id="sequential",
                                                              ctx=ast.Load()),
                                        optional_vars=None)],
                    body=inlined.body),
                node)
            self._insertion_point.append(seq)
            return ast.copy_location(ast.Name(retval_name_m, ast.Load()),
                                     node)
        else:
            arg1 = ast.copy_location(ast.Str("rpc"), node)
            arg2 = ast.copy_location(
                value_to_ast(self.mappers.rpc.encode(func)), node)
            node.args[0:0] = [arg1, arg2]
            node.func = ast.copy_location(
                ast.Name("syscall", ast.Load()), node)
            return node

    def code_visit_Return(self, node):
        self.code_generic_visit(node)
        if self.retval_name is None:
            return node
        else:
            return ast.copy_location(
                ast.Assign(targets=[ast.Name(self.retval_name, ast.Store())],
                           value=node.value),
                node)

    def code_visit_Expr(self, node):
        if isinstance(node.value, ast.Str):
            # Strip docstrings. This also removes strings appearing in the
            # middle of the code, but they are nops.
            return None
        self.code_generic_visit(node)
        if isinstance(node.value, ast.Name):
            # Remove Expr nodes that contain only a name, likely due to
            # function call inlining. Such nodes that were originally in the
            # code are also removed, but this does not affect the semantics of
            # the code as they are nops.
            return None
        else:
            return node

    def encode_exception(self, e):
        exception_class = self.static_visit(e)
        if not inspect.isclass(exception_class):
            raise NotImplementedError("Exception type must be a class")
        if issubclass(exception_class, core_language.RuntimeException):
            exception_id = exception_class.eid
        else:
            exception_id = self.mappers.exception.encode(exception_class)
        return ast.copy_location(
            ast.Call(func=ast.Name("EncodedException", ast.Load()),
                     args=[value_to_ast(exception_id)],
                     keywords=[], starargs=None, kwargs=None),
            e)

    def code_visit_Raise(self, node):
        if node.cause is not None:
            raise NotImplementedError("Exception causes are not supported")
        if node.exc is not None:
            node.exc = self.encode_exception(node.exc)
        return node

    def code_visit_ExceptHandler(self, node):
        if node.name is not None:
            raise NotImplementedError("'as target' is not supported")
        if node.type is not None:
            if isinstance(node.type, ast.Tuple):
                node.type.elts = [self.encode_exception(e)
                                  for e in node.type.elts]
            else:
                node.type = self.encode_exception(node.type)
        self.code_generic_visit(node)
        return node

    def code_visit_FunctionDef(self, node):
        node.args = ast.arguments(args=[], vararg=None, kwonlyargs=[],
                                  kw_defaults=[], kwarg=None, defaults=[])
        node.decorator_list = []
        self.code_generic_visit(node)
        return node

    def static_visit(self, node):
        method = "static_visit_" + node.__class__.__name__
        visitor = getattr(self, method)
        return visitor(node)

    def static_visit_Name(self, node):
        try:
            obj = self.local_namespace[node.id]
        except KeyError:
            try:
                obj = self.global_namespace[node.id]
            except KeyError:
                raise NameError("name '{}' is not defined".format(node.id))
        if isinstance(obj, MangledName):
            raise NotImplementedError(
                "Only a static object can be used here")
        return obj

    def static_visit_Attribute(self, node):
        value = self.static_visit(node.value)
        return getattr(value, node.attr)


class HostObjectMapper:
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


def get_attr_init(attribute_namespace, loc_node):
    attr_init = []
    for (_, attr), attr_info in attribute_namespace.items():
        if hasattr(attr_info.obj, attr):
            value = getattr(attr_info.obj, attr)
            if (hasattr(value, "kernel_attr_init")
                    and not value.kernel_attr_init):
                continue
            value = ast.copy_location(value_to_ast(value), loc_node)
            target = ast.copy_location(ast.Name(attr_info.mangled_name,
                                                ast.Store()),
                                       loc_node)
            assign = ast.copy_location(ast.Assign([target], value),
                                       loc_node)
            attr_init.append(assign)
    return attr_init


def get_attr_writeback(attribute_namespace, rpc_mapper, loc_node):
    attr_writeback = []
    for (_, attr), attr_info in attribute_namespace.items():
        if attr_info.read_write:
            setter = partial(setattr, attr_info.obj, attr)
            func = ast.copy_location(
                ast.Name("syscall", ast.Load()), loc_node)
            arg1 = ast.copy_location(ast.Str("rpc"), loc_node)
            arg2 = ast.copy_location(
                value_to_ast(rpc_mapper.encode(setter)), loc_node)
            arg3 = ast.copy_location(
                ast.Name(attr_info.mangled_name, ast.Load()), loc_node)
            call = ast.copy_location(
                ast.Call(func=func, args=[arg1, arg2, arg3],
                         keywords=[], starargs=None, kwargs=None),
                loc_node)
            expr = ast.copy_location(ast.Expr(call), loc_node)
            attr_writeback.append(expr)
    return attr_writeback


def inline(core, k_function, k_args, k_kwargs):
    # OrderedDict prevents non-determinism in attribute init
    attribute_namespace = OrderedDict()
    in_use_names = copy(embeddable_func_names)
    mappers = types.SimpleNamespace(
        rpc=HostObjectMapper(),
        exception=HostObjectMapper(core_language.first_user_eid)
    )
    func_def = get_inline(
        core=core,
        attribute_namespace=attribute_namespace,
        in_use_names=in_use_names,
        retval_name=None,
        mappers=mappers,
        func=k_function,
        args=k_args,
        kwargs=k_kwargs)

    func_def.body[0:0] = get_attr_init(attribute_namespace, func_def)
    func_def.body += get_attr_writeback(attribute_namespace, mappers.rpc,
                                        func_def)

    return func_def, mappers.rpc.get_map(), mappers.exception.get_map()
