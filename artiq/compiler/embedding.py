"""
The :class:`Stitcher` class allows to transparently combine compiled
Python code and Python code executed on the host system: it resolves
the references to the host objects and translates the functions
annotated as ``@kernel`` when they are referenced.
"""

import sys, os, re, linecache, inspect, textwrap, types as pytypes, numpy
from collections import OrderedDict, defaultdict

from pythonparser import ast, algorithm, source, diagnostic, parse_buffer
from pythonparser import lexer as source_lexer, parser as source_parser

from Levenshtein import ratio as similarity, jaro_winkler

from ..language import core as language_core
from . import types, builtins, asttyped, prelude
from .transforms import ASTTypedRewriter, Inferencer, IntMonomorphizer, TypedtreePrinter
from .transforms.asttyped_rewriter import LocalExtractor


class SpecializedFunction:
    def __init__(self, instance_type, host_function):
        self.instance_type = instance_type
        self.host_function = host_function

    def __eq__(self, other):
        if isinstance(other, tuple):
            return (self.instance_type == other[0] or
                    self.host_function == other[1])
        else:
            return (self.instance_type == other.instance_type or
                    self.host_function == other.host_function)

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        return hash((self.instance_type, self.host_function))


class EmbeddingMap:
    def __init__(self):
        self.object_current_key = 0
        self.object_forward_map = {}
        self.object_reverse_map = {}
        self.module_map = {}
        self.type_map = {}
        self.function_map = {}

    # Modules
    def store_module(self, module, module_type):
        self.module_map[module] = module_type

    def retrieve_module(self, module):
        return self.module_map[module]

    def has_module(self, module):
        return module in self.module_map

    # Types
    def store_type(self, host_type, instance_type, constructor_type):
        self._rename_type(instance_type)
        self.type_map[host_type] = (instance_type, constructor_type)

    def retrieve_type(self, host_type):
        return self.type_map[host_type]

    def has_type(self, host_type):
        return host_type in self.type_map

    def _rename_type(self, new_instance_type):
        # Generally, user-defined types that have exact same name (which is to say, classes
        # defined inside functions) do not pose a problem to the compiler. The two places which
        # cannot handle this are:
        #  1. {TInstance,TConstructor}.__hash__
        #  2. LLVM type names
        # Since handling #2 requires renaming on ARTIQ side anyway, it's more straightforward
        # to do it once when embedding (since non-embedded code cannot define classes in
        # functions). Also, easier to debug.
        n = 0
        for host_type in self.type_map:
            instance_type, constructor_type = self.type_map[host_type]
            if instance_type.name == new_instance_type.name:
                n += 1
                new_instance_type.name = "{}.{}".format(new_instance_type.name, n)

    def attribute_count(self):
        count = 0
        for host_type in self.type_map:
            instance_type, constructor_type = self.type_map[host_type]
            count += len(instance_type.attributes)
            count += len(constructor_type.attributes)
        return count

    # Functions
    def store_function(self, function, ir_function_name):
        self.function_map[function] = ir_function_name

    def retrieve_function(self, function):
        return self.function_map[function]

    def specialize_function(self, instance_type, host_function):
        return SpecializedFunction(instance_type, host_function)

    # Objects
    def store_object(self, obj_ref):
        obj_id = id(obj_ref)
        if obj_id in self.object_reverse_map:
            return self.object_reverse_map[obj_id]

        self.object_current_key += 1
        self.object_forward_map[self.object_current_key] = obj_ref
        self.object_reverse_map[obj_id] = self.object_current_key
        return self.object_current_key

    def retrieve_object(self, obj_key):
        return self.object_forward_map[obj_key]

    def iter_objects(self):
        for obj_id in self.object_forward_map.keys():
            obj_ref = self.object_forward_map[obj_id]
            if isinstance(obj_ref, (pytypes.FunctionType, pytypes.MethodType,
                                    pytypes.BuiltinFunctionType, pytypes.ModuleType,
                                    SpecializedFunction)):
                continue
            elif isinstance(obj_ref, type):
                _, obj_typ = self.type_map[obj_ref]
            else:
                obj_typ, _ = self.type_map[type(obj_ref)]
            yield obj_id, obj_ref, obj_typ

    def has_rpc(self):
        return any(filter(lambda x: inspect.isfunction(x) or inspect.ismethod(x),
                          self.object_forward_map.values()))


class ASTSynthesizer:
    def __init__(self, embedding_map, value_map, quote_function=None, expanded_from=None):
        self.source = ""
        self.source_buffer = source.Buffer(self.source, "<synthesized>")
        self.embedding_map = embedding_map
        self.value_map = value_map
        self.quote_function = quote_function
        self.expanded_from = expanded_from
        self.diagnostics = []

    def finalize(self):
        self.source_buffer.source = self.source
        return self.source_buffer

    def _add(self, fragment):
        range_from   = len(self.source)
        self.source += fragment
        range_to     = len(self.source)
        return source.Range(self.source_buffer, range_from, range_to,
                            expanded_from=self.expanded_from)

    def quote(self, value):
        """Construct an AST fragment equal to `value`."""
        if value is None:
            typ = builtins.TNone()
            return asttyped.NameConstantT(value=value, type=typ,
                                          loc=self._add(repr(value)))
        elif value is True or value is False:
            typ = builtins.TBool()
            return asttyped.NameConstantT(value=value, type=typ,
                                          loc=self._add(repr(value)))
        elif value is numpy.int32:
            typ = builtins.fn_int32()
            return asttyped.NameConstantT(value=None, type=typ,
                                          loc=self._add("numpy.int32"))
        elif value is numpy.int64:
            typ = builtins.fn_int64()
            return asttyped.NameConstantT(value=None, type=typ,
                                          loc=self._add("numpy.int64"))
        elif value is numpy.array:
            typ = builtins.fn_array()
            return asttyped.NameConstantT(value=None, type=typ,
                                          loc=self._add("numpy.array"))
        elif value is numpy.full:
            typ = builtins.fn_make_array()
            return asttyped.NameConstantT(value=None, type=typ,
                                          loc=self._add("numpy.full"))
        elif isinstance(value, (int, float)):
            if isinstance(value, int):
                typ = builtins.TInt()
            elif isinstance(value, float):
                typ = builtins.TFloat()
            return asttyped.NumT(n=value, ctx=None, type=typ,
                                 loc=self._add(repr(value)))
        elif isinstance(value, numpy.int32):
            typ = builtins.TInt32()
            return asttyped.NumT(n=int(value), ctx=None, type=typ,
                                 loc=self._add(repr(value)))
        elif isinstance(value, numpy.int64):
            typ = builtins.TInt64()
            return asttyped.NumT(n=int(value), ctx=None, type=typ,
                                 loc=self._add(repr(value)))
        elif isinstance(value, str):
            return asttyped.StrT(s=value, ctx=None, type=builtins.TStr(),
                                 loc=self._add(repr(value)))
        elif isinstance(value, bytes):
            return asttyped.StrT(s=value, ctx=None, type=builtins.TBytes(),
                                 loc=self._add(repr(value)))
        elif isinstance(value, bytearray):
            quote_loc   = self._add('`')
            repr_loc    = self._add(repr(value))
            unquote_loc = self._add('`')
            loc         = quote_loc.join(unquote_loc)

            return asttyped.QuoteT(value=value, type=builtins.TByteArray(), loc=loc)
        elif isinstance(value, list):
            begin_loc = self._add("[")
            elts = []
            for index, elt in enumerate(value):
                elts.append(self.quote(elt))
                if index < len(value) - 1:
                    self._add(", ")
            end_loc   = self._add("]")
            return asttyped.ListT(elts=elts, ctx=None, type=builtins.TList(),
                                  begin_loc=begin_loc, end_loc=end_loc,
                                  loc=begin_loc.join(end_loc))
        elif isinstance(value, tuple):
            begin_loc = self._add("(")
            elts = []
            for index, elt in enumerate(value):
                elts.append(self.quote(elt))
                self._add(", ")
            end_loc   = self._add(")")
            return asttyped.TupleT(elts=elts, ctx=None,
                                   type=types.TTuple([e.type for e in elts]),
                                   begin_loc=begin_loc, end_loc=end_loc,
                                   loc=begin_loc.join(end_loc))
        elif isinstance(value, numpy.ndarray):
            begin_loc = self._add("numpy.array([")
            elts = []
            for index, elt in enumerate(value):
                elts.append(self.quote(elt))
                if index < len(value) - 1:
                    self._add(", ")
            end_loc   = self._add("])")

            return asttyped.ListT(elts=elts, ctx=None, type=builtins.TArray(),
                                  begin_loc=begin_loc, end_loc=end_loc,
                                  loc=begin_loc.join(end_loc))
        elif inspect.isfunction(value) or inspect.ismethod(value) or \
                isinstance(value, pytypes.BuiltinFunctionType) or \
                isinstance(value, SpecializedFunction):
            if inspect.ismethod(value):
                quoted_self   = self.quote(value.__self__)
                function_type = self.quote_function(value.__func__, self.expanded_from)
                method_type   = types.TMethod(quoted_self.type, function_type)

                dot_loc     = self._add('.')
                name_loc    = self._add(value.__func__.__name__)
                loc         = quoted_self.loc.join(name_loc)
                return asttyped.QuoteT(value=value, type=method_type,
                                       self_loc=quoted_self.loc, loc=loc)
            else: # function
                function_type = self.quote_function(value, self.expanded_from)

                quote_loc   = self._add('`')
                repr_loc    = self._add(repr(value))
                unquote_loc = self._add('`')
                loc         = quote_loc.join(unquote_loc)
                return asttyped.QuoteT(value=value, type=function_type, loc=loc)
        elif isinstance(value, pytypes.ModuleType):
            if self.embedding_map.has_module(value):
                module_type = self.embedding_map.retrieve_module(value)
            else:
                module_type = types.TModule(value.__name__, OrderedDict())
                module_type.attributes['__objectid__'] = builtins.TInt32()
                self.embedding_map.store_module(value, module_type)

            quote_loc   = self._add('`')
            repr_loc    = self._add(repr(value))
            unquote_loc = self._add('`')
            loc         = quote_loc.join(unquote_loc)

            self.value_map[module_type].append((value, loc))
            return asttyped.QuoteT(value=value, type=module_type, loc=loc)
        else:
            quote_loc   = self._add('`')
            repr_loc    = self._add(repr(value))
            unquote_loc = self._add('`')
            loc         = quote_loc.join(unquote_loc)

            if isinstance(value, type):
                typ = value
            else:
                typ = type(value)

            if self.embedding_map.has_type(typ):
                instance_type, constructor_type = self.embedding_map.retrieve_type(typ)

                if hasattr(value, 'kernel_invariants') and \
                        value.kernel_invariants != instance_type.constant_attributes:
                    attr_diff = value.kernel_invariants.difference(
                                    instance_type.constant_attributes)
                    if len(attr_diff) > 0:
                        diag = diagnostic.Diagnostic("warning",
                            "object {value} of type {typ} declares attribute(s) {attrs} as "
                            "kernel invariant, but other objects of the same type do not; "
                            "the invariant annotation on this object will be ignored",
                            {"value": repr(value),
                             "typ": types.TypePrinter().name(instance_type, max_depth=0),
                             "attrs": ", ".join(["'{}'".format(attr) for attr in attr_diff])},
                            loc)
                        self.diagnostics.append(diag)
                    attr_diff = instance_type.constant_attributes.difference(
                                    value.kernel_invariants)
                    if len(attr_diff) > 0:
                        diag = diagnostic.Diagnostic("warning",
                            "object {value} of type {typ} does not declare attribute(s) {attrs} as "
                            "kernel invariant, but other objects of the same type do; "
                            "the invariant annotation on other objects will be ignored",
                            {"value": repr(value),
                             "typ": types.TypePrinter().name(instance_type, max_depth=0),
                             "attrs": ", ".join(["'{}'".format(attr) for attr in attr_diff])},
                            loc)
                        self.diagnostics.append(diag)
                    value.kernel_invariants = value.kernel_invariants.intersection(
                                        instance_type.constant_attributes)
            else:
                if issubclass(typ, BaseException):
                    if hasattr(typ, 'artiq_builtin'):
                        exception_id = 0
                    else:
                        exception_id = self.embedding_map.store_object(typ)
                    instance_type = builtins.TException("{}.{}".format(typ.__module__,
                                                                       typ.__qualname__),
                                                        id=exception_id)
                    constructor_type = types.TExceptionConstructor(instance_type)
                else:
                    instance_type = types.TInstance("{}.{}".format(typ.__module__, typ.__qualname__),
                                                    OrderedDict())
                    instance_type.attributes['__objectid__'] = builtins.TInt32()
                    constructor_type = types.TConstructor(instance_type)
                constructor_type.attributes['__objectid__'] = builtins.TInt32()
                instance_type.constructor = constructor_type

                self.embedding_map.store_type(typ, instance_type, constructor_type)

                if hasattr(value, 'kernel_invariants'):
                    assert isinstance(value.kernel_invariants, set)
                    instance_type.constant_attributes = value.kernel_invariants

            if isinstance(value, type):
                self.value_map[constructor_type].append((value, loc))
                return asttyped.QuoteT(value=value, type=constructor_type,
                                       loc=loc)
            else:
                self.value_map[instance_type].append((value, loc))
                return asttyped.QuoteT(value=value, type=instance_type,
                                       loc=loc)

    def call(self, callee, args, kwargs, callback=None):
        """
        Construct an AST fragment calling a function specified by
        an AST node `function_node`, with given arguments.
        """
        if callback is not None:
            callback_node = self.quote(callback)
            cb_begin_loc  = self._add("(")

        callee_node = self.quote(callee)
        arg_nodes   = []
        kwarg_nodes = []
        kwarg_locs  = []

        begin_loc      = self._add("(")
        for index, arg in enumerate(args):
            arg_nodes.append(self.quote(arg))
            if index < len(args) - 1:
                         self._add(", ")
        if any(args) and any(kwargs):
                         self._add(", ")
        for index, kw in enumerate(kwargs):
            arg_loc    = self._add(kw)
            equals_loc = self._add("=")
            kwarg_locs.append((arg_loc, equals_loc))
            kwarg_nodes.append(self.quote(kwargs[kw]))
            if index < len(kwargs) - 1:
                         self._add(", ")
        end_loc        = self._add(")")

        if callback is not None:
            cb_end_loc    = self._add(")")

        node = asttyped.CallT(
            func=callee_node,
            args=arg_nodes,
            keywords=[ast.keyword(arg=kw, value=value,
                                  arg_loc=arg_loc, equals_loc=equals_loc,
                                  loc=arg_loc.join(value.loc))
                      for kw, value, (arg_loc, equals_loc)
                       in zip(kwargs, kwarg_nodes, kwarg_locs)],
            starargs=None, kwargs=None,
            type=types.TVar(), iodelay=None, arg_exprs={},
            begin_loc=begin_loc, end_loc=end_loc, star_loc=None, dstar_loc=None,
            loc=callee_node.loc.join(end_loc))

        if callback is not None:
            node = asttyped.CallT(
                func=callback_node,
                args=[node], keywords=[], starargs=None, kwargs=None,
                type=builtins.TNone(), iodelay=None, arg_exprs={},
                begin_loc=cb_begin_loc, end_loc=cb_end_loc, star_loc=None, dstar_loc=None,
                loc=callback_node.loc.join(cb_end_loc))

        return node


def suggest_identifier(id, names):
    sorted_names = sorted(names, key=lambda other: jaro_winkler(id, other), reverse=True)
    if len(sorted_names) > 0:
        if jaro_winkler(id, sorted_names[0]) > 0.0 and similarity(id, sorted_names[0]) > 0.5:
            return sorted_names[0]

class StitchingASTTypedRewriter(ASTTypedRewriter):
    def __init__(self, engine, prelude, globals, host_environment, quote):
        super().__init__(engine, prelude)
        self.globals = globals
        self.env_stack.append(self.globals)

        self.host_environment = host_environment
        self.quote = quote

    def visit_arg(self, node):
        typ = self._find_name(node.arg, node.loc)
        # ignore annotations; these are handled in _quote_function
        return asttyped.argT(type=typ,
                             arg=node.arg, annotation=None,
                             arg_loc=node.arg_loc, colon_loc=node.colon_loc, loc=node.loc)

    def visit_quoted_function(self, node, function):
        extractor = LocalExtractor(env_stack=self.env_stack, engine=self.engine)
        extractor.visit(node)

        # We quote the defaults so they end up in the global data in LLVM IR.
        # This way there is no "life before main", i.e. they do not have to be
        # constructed before the main translated call executes; but the Python
        # semantics is kept.
        defaults = function.__defaults__ or ()
        quoted_defaults = []
        for default, default_node in zip(defaults, node.args.defaults):
            quoted_defaults.append(self.quote(default, default_node.loc))
        node.args.defaults = quoted_defaults

        node = asttyped.QuotedFunctionDefT(
            typing_env=extractor.typing_env, globals_in_scope=extractor.global_,
            signature_type=types.TVar(), return_type=types.TVar(),
            name=node.name, args=node.args, returns=node.returns,
            body=node.body, decorator_list=node.decorator_list,
            keyword_loc=node.keyword_loc, name_loc=node.name_loc,
            arrow_loc=node.arrow_loc, colon_loc=node.colon_loc, at_locs=node.at_locs,
            loc=node.loc)

        try:
            self.env_stack.append(node.typing_env)
            return self.generic_visit(node)
        finally:
            self.env_stack.pop()

    def visit_Name(self, node):
        typ = super()._try_find_name(node.id)
        if typ is not None:
            # Value from device environment.
            return asttyped.NameT(type=typ, id=node.id, ctx=node.ctx,
                                  loc=node.loc)
        else:
            # Try to find this value in the host environment and quote it.
            if node.id == "print":
                return self.quote(print, node.loc)
            elif node.id in self.host_environment:
                return self.quote(self.host_environment[node.id], node.loc)
            else:
                names = set()
                names.update(self.host_environment.keys())
                for typing_env in reversed(self.env_stack):
                    names.update(typing_env.keys())

                suggestion = suggest_identifier(node.id, names)
                if suggestion is not None:
                    diag = diagnostic.Diagnostic("fatal",
                        "name '{name}' is not bound to anything; did you mean '{suggestion}'?",
                        {"name": node.id, "suggestion": suggestion},
                        node.loc)
                    self.engine.process(diag)
                else:
                    diag = diagnostic.Diagnostic("fatal",
                        "name '{name}' is not bound to anything", {"name": node.id},
                        node.loc)
                    self.engine.process(diag)

class StitchingInferencer(Inferencer):
    def __init__(self, engine, value_map, quote):
        super().__init__(engine)
        self.value_map = value_map
        self.quote = quote
        self.attr_type_cache = {}

    def _compute_attr_type(self, object_value, object_type, object_loc, attr_name, loc):
        if not hasattr(object_value, attr_name):
            if attr_name.startswith('_'):
                names = set(filter(lambda name: not name.startswith('_'),
                                   dir(object_value)))
            else:
                names = set(dir(object_value))
            suggestion = suggest_identifier(attr_name, names)

            note = diagnostic.Diagnostic("note",
                "attribute accessed here", {},
                loc)
            if suggestion is not None:
                diag = diagnostic.Diagnostic("error",
                    "host object does not have an attribute '{attr}'; "
                    "did you mean '{suggestion}'?",
                    {"attr": attr_name, "suggestion": suggestion},
                    object_loc, notes=[note])
            else:
                diag = diagnostic.Diagnostic("error",
                    "host object does not have an attribute '{attr}'",
                    {"attr": attr_name},
                    object_loc, notes=[note])
            self.engine.process(diag)
            return

        # Figure out what ARTIQ type does the value of the attribute have.
        # We do this by quoting it, as if to serialize. This has some
        # overhead (i.e. synthesizing a source buffer), but has the advantage
        # of having the host-to-ARTIQ mapping code in only one place and
        # also immediately getting proper diagnostics on type errors.
        attr_value = getattr(object_value, attr_name)
        if (inspect.ismethod(attr_value) and
                types.is_instance(object_type) and
                # Check that the method is indeed defined on the class,
                # and not just this instance. The check is written in
                # the inverted form and not as hasattr(type(attr_value))
                # since the method may as well be defined on a superclass.
                attr_name not in object_value.__dict__):
            # In cases like:
            #     class c:
            #         @kernel
            #         def f(self): pass
            # we want f to be defined on the class, not on the instance.
            attributes = object_type.constructor.attributes
            attr_value = SpecializedFunction(object_type, attr_value.__func__)
        else:
            attributes = object_type.attributes

        attr_value_type = None

        if isinstance(attr_value, list):
            # Fast path for lists of scalars.
            IS_FLOAT = 1
            IS_INT32 = 2
            IS_INT64 = 4

            state = 0
            for elt in attr_value:
                if elt.__class__ == float:
                    state |= IS_FLOAT
                elif elt.__class__ == int:
                    if -2**31 < elt < 2**31-1:
                        state |= IS_INT32
                    elif -2**63 < elt < 2**63-1:
                        state |= IS_INT64
                    else:
                        state = -1
                        break
                else:
                    state = -1

            if state == IS_FLOAT:
                attr_value_type = builtins.TList(builtins.TFloat())
            elif state == IS_INT32:
                attr_value_type = builtins.TList(builtins.TInt32())
            elif state == IS_INT64:
                attr_value_type = builtins.TList(builtins.TInt64())

        if attr_value_type is None:
            note = diagnostic.Diagnostic("note",
                "while inferring a type for an attribute '{attr}' of a host object",
                {"attr": attr_name},
                loc)

            with self.engine.context(note):
                # Slow path. We don't know what exactly is the attribute value,
                # so we quote it only for the error message that may possibly result.
                ast = self.quote(attr_value, object_loc.expanded_from)
                Inferencer(engine=self.engine).visit(ast)
                IntMonomorphizer(engine=self.engine).visit(ast)
                attr_value_type = ast.type

        return attributes, attr_value_type

    def _unify_attribute(self, result_type, value_node, attr_name, attr_loc, loc):
        # The inferencer can only observe types, not values; however,
        # when we work with host objects, we have to get the values
        # somewhere, since host interpreter does not have types.
        # Since we have categorized every host object we quoted according to
        # its type, we now interrogate every host object we have to ensure
        # that we can successfully serialize the value of the attribute we
        # are now adding at the code generation stage.
        object_type = value_node.type.find()
        for object_value, object_loc in self.value_map[object_type]:
            attr_type_key = (id(object_value), attr_name)
            try:
                attributes, attr_value_type = self.attr_type_cache[attr_type_key]
            except KeyError:
                attributes, attr_value_type = \
                    self._compute_attr_type(object_value, object_type, object_loc, attr_name, loc)
                self.attr_type_cache[attr_type_key] = attributes, attr_value_type

            if attr_name not in attributes:
                # We just figured out what the type should be. Add it.
                attributes[attr_name] = attr_value_type
            else:
                # Does this conflict with an earlier guess?
                try:
                    attributes[attr_name].unify(attr_value_type)
                except types.UnificationError as e:
                    printer = types.TypePrinter()
                    diag = diagnostic.Diagnostic("error",
                        "host object has an attribute '{attr}' of type {typea}, which is"
                        " different from previously inferred type {typeb} for the same attribute",
                        {"typea": printer.name(attr_value_type),
                         "typeb": printer.name(attributes[attr_name]),
                         "attr": attr_name},
                        object_loc)
                    self.engine.process(diag)

        super()._unify_attribute(result_type, value_node, attr_name, attr_loc, loc)

    def visit_QuoteT(self, node):
        if inspect.ismethod(node.value):
            if types.is_rpc(types.get_method_function(node.type)):
                return
            self._unify_method_self(method_type=node.type,
                                    attr_name=node.value.__func__.__name__,
                                    attr_loc=None,
                                    loc=node.loc,
                                    self_loc=node.self_loc)

class TypedtreeHasher(algorithm.Visitor):
    def generic_visit(self, node):
        def freeze(obj):
            if isinstance(obj, ast.AST):
                return self.visit(obj)
            elif isinstance(obj, list):
                return hash(tuple(freeze(elem) for elem in obj))
            elif isinstance(obj, types.Type):
                return hash(obj.find())
            else:
                # We don't care; only types change during inference.
                pass

        fields = node._fields
        if hasattr(node, '_types'):
            fields = fields + node._types
        return hash(tuple(freeze(getattr(node, field_name)) for field_name in fields))

class Stitcher:
    def __init__(self, core, dmgr, engine=None, print_as_rpc=True):
        self.core = core
        self.dmgr = dmgr
        if engine is None:
            self.engine = diagnostic.Engine(all_errors_are_fatal=True)
        else:
            self.engine = engine

        self.name = ""
        self.typedtree = []
        self.inject_at = 0
        self.globals = {}

        # We don't want some things from the prelude as they are provided in
        # the host Python namespace and gain special meaning when quoted.
        self.prelude = prelude.globals()
        if print_as_rpc:
            self.prelude.pop("print")
        self.prelude.pop("array")

        self.functions = {}

        self.embedding_map = EmbeddingMap()
        self.value_map = defaultdict(lambda: [])

    def stitch_call(self, function, args, kwargs, callback=None):
        # We synthesize source code for the initial call so that
        # diagnostics would have something meaningful to display to the user.
        synthesizer = self._synthesizer(self._function_loc(function.artiq_embedded.function))
        call_node = synthesizer.call(function, args, kwargs, callback)
        synthesizer.finalize()
        self.typedtree.append(call_node)

    def finalize(self):
        inferencer = StitchingInferencer(engine=self.engine,
                                         value_map=self.value_map,
                                         quote=self._quote)
        typedtree_hasher = TypedtreeHasher()

        # Iterate inference to fixed point.
        old_typedtree_hash = None
        old_attr_count = None
        while True:
            inferencer.visit(self.typedtree)
            typedtree_hash = typedtree_hasher.visit(self.typedtree)
            attr_count = self.embedding_map.attribute_count()

            if old_typedtree_hash == typedtree_hash and old_attr_count == attr_count:
                break
            old_typedtree_hash = typedtree_hash
            old_attr_count = attr_count

        # After we've discovered every referenced attribute, check if any kernel_invariant
        # specifications refers to ones we didn't encounter.
        for host_type in self.embedding_map.type_map:
            instance_type, constructor_type = self.embedding_map.type_map[host_type]
            if not hasattr(instance_type, "constant_attributes"):
                # Exceptions lack user-definable attributes.
                continue

            for attribute in instance_type.constant_attributes:
                if attribute in instance_type.attributes:
                    # Fast path; if the ARTIQ Python type has the attribute, then every observed
                    # value is guaranteed to have it too.
                    continue

                for value, loc in self.value_map[instance_type]:
                    if hasattr(value, attribute):
                        continue

                    diag = diagnostic.Diagnostic("warning",
                        "object {value} of type {typ} declares attribute '{attr}' as "
                        "kernel invariant, but the instance referenced here does not "
                        "have this attribute",
                        {"value": repr(value),
                         "typ": types.TypePrinter().name(instance_type, max_depth=0),
                         "attr": attribute},
                        loc)
                    self.engine.process(diag)

        # After we have found all functions, synthesize a module to hold them.
        source_buffer = source.Buffer("", "<synthesized>")
        self.typedtree = asttyped.ModuleT(
            typing_env=self.globals, globals_in_scope=set(),
            body=self.typedtree, loc=source.Range(source_buffer, 0, 0))

    def _inject(self, node):
        self.typedtree.insert(self.inject_at, node)
        self.inject_at += 1

    def _synthesizer(self, expanded_from=None):
        return ASTSynthesizer(expanded_from=expanded_from,
                              embedding_map=self.embedding_map,
                              value_map=self.value_map,
                              quote_function=self._quote_function)

    def _function_loc(self, function):
        if isinstance(function, SpecializedFunction):
            function = function.host_function
        if hasattr(function, 'artiq_embedded') and function.artiq_embedded.function:
            function = function.artiq_embedded.function

        if isinstance(function, str):
            return source.Range(source.Buffer(function, "<string>"), 0, 0)

        filename = function.__code__.co_filename
        line     = function.__code__.co_firstlineno
        name     = function.__code__.co_name

        source_line = linecache.getline(filename, line).lstrip()
        while source_line.startswith("@") or source_line == "":
            line += 1
            source_line = linecache.getline(filename, line).lstrip()

        if "<lambda>" in function.__qualname__:
            column = 0 # can't get column of lambda
        else:
            column = re.search("def", source_line).start(0)
        source_buffer = source.Buffer(source_line, filename, line)
        return source.Range(source_buffer, column, column)

    def _call_site_note(self, call_loc, fn_kind):
        if call_loc:
            if fn_kind == 'syscall':
                return [diagnostic.Diagnostic("note",
                    "in system call here", {},
                    call_loc)]
            elif fn_kind == 'rpc':
                return [diagnostic.Diagnostic("note",
                    "in function called remotely here", {},
                    call_loc)]
            elif fn_kind == 'kernel':
                return [diagnostic.Diagnostic("note",
                    "in kernel function here", {},
                    call_loc)]
            else:
                assert False
        else:
            return []

    def _type_of_param(self, function, loc, param, fn_kind):
        if param.annotation is not inspect.Parameter.empty:
            # Type specified explicitly.
            return self._extract_annot(function, param.annotation,
                                       "argument '{}'".format(param.name), loc,
                                       fn_kind)
        elif fn_kind == 'syscall':
            # Syscalls must be entirely annotated.
            diag = diagnostic.Diagnostic("error",
                "system call argument '{argument}' must have a type annotation",
                {"argument": param.name},
                self._function_loc(function),
                notes=self._call_site_note(loc, fn_kind))
            self.engine.process(diag)
        elif fn_kind == 'rpc' and param.default is not inspect.Parameter.empty:
            notes = []
            notes.append(diagnostic.Diagnostic("note",
                "expanded from here while trying to infer a type for an"
                " unannotated optional argument '{argument}' from its default value",
                {"argument": param.name},
                self._function_loc(function)))
            if loc is not None:
                notes.append(self._call_site_note(loc, fn_kind))

            with self.engine.context(*notes):
                # Try and infer the type from the default value.
                # This is tricky, because the default value might not have
                # a well-defined type in APython.
                # In this case, we bail out, but mention why we do it.
                ast = self._quote(param.default, None)
                Inferencer(engine=self.engine).visit(ast)
                IntMonomorphizer(engine=self.engine).visit(ast)
                return ast.type
        else:
            # Let the rest of the program decide.
            return types.TVar()

    def _quote_embedded_function(self, function, flags):
        if isinstance(function, SpecializedFunction):
            host_function = function.host_function
        else:
            host_function = function

        if not hasattr(host_function, "artiq_embedded"):
            raise ValueError("{} is not an embedded function".format(repr(host_function)))

        # Extract function source.
        embedded_function = host_function.artiq_embedded.function
        if isinstance(embedded_function, str):
            # This is a function to be eval'd from the given source code in string form.
            # Mangle the host function's id() into the fully qualified name to make sure
            # there are no collisions.
            source_code = embedded_function
            embedded_function = host_function
            filename = "<string>"
            module_name = "__eval_{}".format(id(host_function))
            first_line = 1
        else:
            source_code = inspect.getsource(embedded_function)
            filename = embedded_function.__code__.co_filename
            module_name = embedded_function.__globals__['__name__']
            first_line = embedded_function.__code__.co_firstlineno

        # Extract function annotation.
        signature = inspect.signature(embedded_function)
        loc = self._function_loc(embedded_function)

        arg_types = OrderedDict()
        optarg_types = OrderedDict()
        for param in signature.parameters.values():
            if param.kind == inspect.Parameter.VAR_POSITIONAL or \
                    param.kind == inspect.Parameter.VAR_KEYWORD:
                diag = diagnostic.Diagnostic("error",
                    "variadic arguments are not supported; '{argument}' is variadic",
                    {"argument": param.name},
                    self._function_loc(function),
                    notes=self._call_site_note(loc, fn_kind='kernel'))
                self.engine.process(diag)

            arg_type = self._type_of_param(function, loc, param, fn_kind='kernel')
            if param.default is inspect.Parameter.empty:
                arg_types[param.name] = arg_type
            else:
                optarg_types[param.name] = arg_type

        if signature.return_annotation is not inspect.Signature.empty:
            ret_type = self._extract_annot(function, signature.return_annotation,
                                           "return type", loc, fn_kind='kernel')
        else:
            ret_type = types.TVar()

        # Extract function environment.
        host_environment = dict()
        host_environment.update(embedded_function.__globals__)
        cells = embedded_function.__closure__
        cell_names = embedded_function.__code__.co_freevars
        host_environment.update({var: cells[index] for index, var in enumerate(cell_names)})

        # Find out how indented we are.
        initial_whitespace = re.search(r"^\s*", source_code).group(0)
        initial_indent = len(initial_whitespace.expandtabs())

        # Parse.
        source_buffer = source.Buffer(source_code, filename, first_line)
        lexer = source_lexer.Lexer(source_buffer, version=sys.version_info[0:2],
                                   diagnostic_engine=self.engine)
        lexer.indent = [(initial_indent,
                         source.Range(source_buffer, 0, len(initial_whitespace)),
                         initial_whitespace)]
        parser = source_parser.Parser(lexer, version=sys.version_info[0:2],
                                      diagnostic_engine=self.engine)
        function_node = parser.file_input().body[0]

        # Mangle the name, since we put everything into a single module.
        full_function_name = "{}.{}".format(module_name, host_function.__qualname__)
        if isinstance(function, SpecializedFunction):
            instance_type = function.instance_type
            function_node.name = "_Z{}{}I{}{}Ezz".format(len(full_function_name), full_function_name,
                                                         len(instance_type.name), instance_type.name)
        else:
            function_node.name = "_Z{}{}zz".format(len(full_function_name), full_function_name)

        # Record the function in the function map so that LLVM IR generator
        # can handle quoting it.
        self.embedding_map.store_function(function, function_node.name)

        # Fill in the function type before typing it to handle recursive
        # invocations.
        self.functions[function] = types.TFunction(arg_types, optarg_types, ret_type)

        # Rewrite into typed form.
        asttyped_rewriter = StitchingASTTypedRewriter(
            engine=self.engine, prelude=self.prelude,
            globals=self.globals, host_environment=host_environment,
            quote=self._quote)
        function_node = asttyped_rewriter.visit_quoted_function(function_node, embedded_function)
        function_node.flags = flags

        # Add it into our typedtree so that it gets inferenced and codegen'd.
        self._inject(function_node)

        # Tie the typing knot.
        self.functions[function].unify(function_node.signature_type)

        return function_node

    def _extract_annot(self, function, annot, kind, call_loc, fn_kind):
        if annot is None:
            annot = builtins.TNone()

        if not isinstance(annot, types.Type):
            diag = diagnostic.Diagnostic("error",
                "type annotation for {kind}, '{annot}', is not an ARTIQ type",
                {"kind": kind, "annot": repr(annot)},
                self._function_loc(function),
                notes=self._call_site_note(call_loc, fn_kind))
            self.engine.process(diag)

            return types.TVar()
        else:
            return annot

    def _quote_syscall(self, function, loc):
        signature = inspect.signature(function)

        arg_types = OrderedDict()
        optarg_types = OrderedDict()
        for param in signature.parameters.values():
            if param.kind != inspect.Parameter.POSITIONAL_OR_KEYWORD:
                diag = diagnostic.Diagnostic("error",
                    "system calls must only use positional arguments; '{argument}' isn't",
                    {"argument": param.name},
                    self._function_loc(function),
                    notes=self._call_site_note(loc, fn_kind='syscall'))
                self.engine.process(diag)

            if param.default is inspect.Parameter.empty:
                arg_types[param.name] = self._type_of_param(function, loc, param,
                                                            fn_kind='syscall')
            else:
                diag = diagnostic.Diagnostic("error",
                    "system call argument '{argument}' must not have a default value",
                    {"argument": param.name},
                    self._function_loc(function),
                    notes=self._call_site_note(loc, fn_kind='syscall'))
                self.engine.process(diag)

        if signature.return_annotation is not inspect.Signature.empty:
            ret_type = self._extract_annot(function, signature.return_annotation,
                                           "return type", loc, fn_kind='syscall')
        else:
            diag = diagnostic.Diagnostic("error",
                "system call must have a return type annotation", {},
                self._function_loc(function),
                notes=self._call_site_note(loc, fn_kind='syscall'))
            self.engine.process(diag)
            ret_type = types.TVar()

        function_type = types.TCFunction(arg_types, ret_type,
                                         name=function.artiq_embedded.syscall,
                                         flags=function.artiq_embedded.flags)
        self.functions[function] = function_type
        return function_type

    def _quote_rpc(self, function, loc):
        if isinstance(function, SpecializedFunction):
            host_function = function.host_function
        else:
            host_function = function
        ret_type = builtins.TNone()

        if isinstance(host_function, pytypes.BuiltinFunctionType):
            pass
        elif (isinstance(host_function, pytypes.FunctionType) or \
              isinstance(host_function, pytypes.MethodType)):
            if isinstance(host_function, pytypes.FunctionType):
                signature = inspect.signature(host_function)
            else:
                # inspect bug?
                signature = inspect.signature(host_function.__func__)
            if signature.return_annotation is not inspect.Signature.empty:
                ret_type = self._extract_annot(host_function, signature.return_annotation,
                                               "return type", loc, fn_kind='rpc')
        else:
            assert False

        is_async = False
        if hasattr(host_function, "artiq_embedded") and \
                "async" in host_function.artiq_embedded.flags:
            is_async = True

        if not builtins.is_none(ret_type) and is_async:
            note = diagnostic.Diagnostic("note",
                "function called here", {},
                loc)
            diag = diagnostic.Diagnostic("fatal",
                "functions that return a value cannot be defined as async RPCs", {},
                self._function_loc(host_function.artiq_embedded.function),
                notes=[note])
            self.engine.process(diag)

        function_type = types.TRPC(ret_type,
                                   service=self.embedding_map.store_object(host_function),
                                   is_async=is_async)
        self.functions[function] = function_type
        return function_type

    def _quote_function(self, function, loc):
        if isinstance(function, SpecializedFunction):
            host_function = function.host_function
        else:
            host_function = function

        if function in self.functions:
            pass
        elif not hasattr(host_function, "artiq_embedded") or \
                (host_function.artiq_embedded.core_name is None and
                 host_function.artiq_embedded.portable is False and
                 host_function.artiq_embedded.syscall is None and
                 host_function.artiq_embedded.forbidden is False):
            self._quote_rpc(function, loc)
        elif host_function.artiq_embedded.function is not None:
            if host_function.__name__ == "<lambda>":
                note = diagnostic.Diagnostic("note",
                    "lambda created here", {},
                    self._function_loc(host_function.artiq_embedded.function))
                diag = diagnostic.Diagnostic("fatal",
                    "lambdas cannot be used as kernel functions", {},
                    loc,
                    notes=[note])
                self.engine.process(diag)

            core_name = host_function.artiq_embedded.core_name
            if core_name is not None and self.dmgr.get(core_name) != self.core:
                note = diagnostic.Diagnostic("note",
                    "called from this function", {},
                    loc)
                diag = diagnostic.Diagnostic("fatal",
                    "this function runs on a different core device '{name}'",
                    {"name": host_function.artiq_embedded.core_name},
                    self._function_loc(host_function.artiq_embedded.function),
                    notes=[note])
                self.engine.process(diag)

            self._quote_embedded_function(function,
                                          flags=host_function.artiq_embedded.flags)
        elif host_function.artiq_embedded.syscall is not None:
            # Insert a storage-less global whose type instructs the compiler
            # to perform a system call instead of a regular call.
            self._quote_syscall(function, loc)
        elif host_function.artiq_embedded.forbidden is not None:
            diag = diagnostic.Diagnostic("fatal",
                "this function cannot be called as an RPC", {},
                self._function_loc(host_function),
                notes=self._call_site_note(loc, fn_kind='rpc'))
            self.engine.process(diag)
        else:
            assert False

        return self.functions[function]

    def _quote(self, value, loc):
        synthesizer = self._synthesizer(loc)
        node = synthesizer.quote(value)
        synthesizer.finalize()
        if len(synthesizer.diagnostics) > 0:
            for warning in synthesizer.diagnostics:
                self.engine.process(warning)
        return node
