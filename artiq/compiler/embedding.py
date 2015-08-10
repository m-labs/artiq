"""
The :class:`Stitcher` class allows to transparently combine compiled
Python code and Python code executed on the host system: it resolves
the references to the host objects and translates the functions
annotated as ``@kernel`` when they are referenced.
"""

import os, re, linecache, inspect
from collections import OrderedDict

from pythonparser import ast, source, diagnostic, parse_buffer

from . import types, builtins, asttyped, prelude
from .transforms import ASTTypedRewriter, Inferencer, IntMonomorphizer


class ASTSynthesizer:
    def __init__(self, expanded_from=None):
        self.source = ""
        self.source_buffer = source.Buffer(self.source, "<synthesized>")
        self.expanded_from = expanded_from

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
        elif isinstance(value, (int, float)):
            if isinstance(value, int):
                typ = builtins.TInt()
            elif isinstance(value, float):
                typ = builtins.TFloat()
            return asttyped.NumT(n=value, ctx=None, type=typ,
                                 loc=self._add(repr(value)))
        elif isinstance(value, str):
            return asttyped.StrT(s=value, ctx=None, type=builtins.TStr(),
                                 loc=self._add(repr(value)))
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
        else:
            raise "no"
            # return asttyped.QuoteT(value=value, type=types.TVar())

    def call(self, function_node, args, kwargs):
        """
        Construct an AST fragment calling a function specified by
        an AST node `function_node`, with given arguments.
        """
        arg_nodes   = []
        kwarg_nodes = []
        kwarg_locs  = []

        name_loc       = self._add(function_node.name)
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

        return asttyped.CallT(
            func=asttyped.NameT(id=function_node.name, ctx=None,
                                type=function_node.signature_type,
                                loc=name_loc),
            args=arg_nodes,
            keywords=[ast.keyword(arg=kw, value=value,
                                  arg_loc=arg_loc, equals_loc=equals_loc,
                                  loc=arg_loc.join(value.loc))
                      for kw, value, (arg_loc, equals_loc)
                       in zip(kwargs, kwarg_nodes, kwarg_locs)],
            starargs=None, kwargs=None,
            type=types.TVar(),
            begin_loc=begin_loc, end_loc=end_loc, star_loc=None, dstar_loc=None,
            loc=name_loc.join(end_loc))

class StitchingASTTypedRewriter(ASTTypedRewriter):
    def __init__(self, engine, prelude, globals, host_environment, quote_function):
        super().__init__(engine, prelude)
        self.globals = globals
        self.env_stack.append(self.globals)

        self.host_environment = host_environment
        self.quote_function = quote_function

    def visit_Name(self, node):
        typ = super()._try_find_name(node.id)
        if typ is not None:
            # Value from device environment.
            return asttyped.NameT(type=typ, id=node.id, ctx=node.ctx,
                                  loc=node.loc)
        else:
            # Try to find this value in the host environment and quote it.
            if node.id in self.host_environment:
                value = self.host_environment[node.id]
                if inspect.isfunction(value):
                    # It's a function. We need to translate the function and insert
                    # a reference to it.
                    function_name = self.quote_function(value, node.loc)
                    return asttyped.NameT(id=function_name, ctx=None,
                                          type=self.globals[function_name],
                                          loc=node.loc)

                else:
                    # It's just a value. Quote it.
                    synthesizer = ASTSynthesizer(expanded_from=node.loc)
                    node = synthesizer.quote(value)
                    synthesizer.finalize()
                    return node
            else:
                diag = diagnostic.Diagnostic("fatal",
                    "name '{name}' is not bound to anything", {"name":node.id},
                    node.loc)
                self.engine.process(diag)

class Stitcher:
    def __init__(self, engine=None):
        if engine is None:
            self.engine = diagnostic.Engine(all_errors_are_fatal=True)
        else:
            self.engine = engine

        self.name = ""
        self.typedtree = []
        self.prelude = prelude.globals()
        self.globals = {}

        self.functions = {}

        self.next_rpc = 0
        self.rpc_map = {}
        self.inverse_rpc_map = {}

    def _map(self, obj):
        obj_id = id(obj)
        if obj_id in self.inverse_rpc_map:
            return self.inverse_rpc_map[obj_id]

        self.next_rpc += 1
        self.rpc_map[self.next_rpc] = obj
        self.inverse_rpc_map[obj_id] = self.next_rpc
        return self.next_rpc

    def finalize(self):
        inferencer = Inferencer(engine=self.engine)

        # Iterate inference to fixed point.
        self.inference_finished = False
        while not self.inference_finished:
            self.inference_finished = True
            inferencer.visit(self.typedtree)

        # After we have found all functions, synthesize a module to hold them.
        source_buffer = source.Buffer("", "<synthesized>")
        self.typedtree = asttyped.ModuleT(
            typing_env=self.globals, globals_in_scope=set(),
            body=self.typedtree, loc=source.Range(source_buffer, 0, 0))

    def _quote_embedded_function(self, function):
        if not hasattr(function, "artiq_embedded"):
            raise ValueError("{} is not an embedded function".format(repr(function)))

        # Extract function source.
        embedded_function = function.artiq_embedded.function
        source_code = inspect.getsource(embedded_function)
        filename = embedded_function.__code__.co_filename
        module_name, _ = os.path.splitext(os.path.basename(filename))
        first_line = embedded_function.__code__.co_firstlineno

        # Extract function environment.
        host_environment = dict()
        host_environment.update(embedded_function.__globals__)
        cells = embedded_function.__closure__
        cell_names = embedded_function.__code__.co_freevars
        host_environment.update({var: cells[index] for index, var in enumerate(cell_names)})

        # Parse.
        source_buffer = source.Buffer(source_code, filename, first_line)
        parsetree, comments = parse_buffer(source_buffer, engine=self.engine)
        function_node = parsetree.body[0]

        # Mangle the name, since we put everything into a single module.
        function_node.name = "{}.{}".format(module_name, function_node.name)

        # Normally, LocalExtractor would populate the typing environment
        # of the module with the function name. However, since we run
        # ASTTypedRewriter on the function node directly, we need to do it
        # explicitly.
        self.globals[function_node.name] = types.TVar()

        # Memoize the function before typing it to handle recursive
        # invocations.
        self.functions[function] = function_node.name

        # Rewrite into typed form.
        asttyped_rewriter = StitchingASTTypedRewriter(
            engine=self.engine, prelude=self.prelude,
            globals=self.globals, host_environment=host_environment,
            quote_function=self._quote_function)
        return asttyped_rewriter.visit(function_node)

    def _function_loc(self, function):
        filename = function.__code__.co_filename
        line     = function.__code__.co_firstlineno
        name     = function.__code__.co_name

        source_line = linecache.getline(filename, line)
        while source_line.lstrip().startswith("@"):
            line += 1
            source_line = linecache.getline(filename, line)

        column = re.search("def", source_line).start(0)
        source_buffer = source.Buffer(source_line, filename, line)
        return source.Range(source_buffer, column, column)

    def _function_def_note(self, function):
        return diagnostic.Diagnostic("note",
            "definition of function '{function}'",
            {"function": function.__name__},
            self._function_loc(function))

    def _extract_annot(self, function, annot, kind, call_loc, is_syscall):
        if not isinstance(annot, types.Type):
            if is_syscall:
                note = diagnostic.Diagnostic("note",
                    "in system call here", {},
                    call_loc)
            else:
                note = diagnostic.Diagnostic("note",
                    "in function called remotely here", {},
                    call_loc)
            diag = diagnostic.Diagnostic("error",
                "type annotation for {kind}, '{annot}', is not an ARTIQ type",
                {"kind": kind, "annot": repr(annot)},
                self._function_loc(function),
                notes=[note])
            self.engine.process(diag)

            return types.TVar()
        else:
            return annot

    def _type_of_param(self, function, loc, param, is_syscall):
        if param.annotation is not inspect.Parameter.empty:
            # Type specified explicitly.
            return self._extract_annot(function, param.annotation,
                                       "argument '{}'".format(param.name), loc,
                                       is_syscall)
        elif is_syscall:
            # Syscalls must be entirely annotated.
            diag = diagnostic.Diagnostic("error",
                "system call argument '{argument}' must have a type annotation",
                {"argument": param.name},
                self._function_loc(function))
            self.engine.process(diag)
        elif param.default is not inspect.Parameter.empty:
            # Try and infer the type from the default value.
            # This is tricky, because the default value might not have
            # a well-defined type in APython.
            # In this case, we bail out, but mention why we do it.
            synthesizer = ASTSynthesizer()
            ast = synthesizer.quote(param.default)
            synthesizer.finalize()

            def proxy_diagnostic(diag):
                note = diagnostic.Diagnostic("note",
                    "expanded from here while trying to infer a type for an"
                    " unannotated optional argument '{argument}' from its default value",
                    {"argument": param.name},
                    loc)
                diag.notes.append(note)

                diag.notes.append(self._function_def_note(function))

                self.engine.process(diag)

            proxy_engine = diagnostic.Engine()
            proxy_engine.process = proxy_diagnostic
            Inferencer(engine=proxy_engine).visit(ast)
            IntMonomorphizer(engine=proxy_engine).visit(ast)

            return ast.type
        else:
            # Let the rest of the program decide.
            return types.TVar()

    def _quote_foreign_function(self, function, loc, syscall):
        signature = inspect.signature(function)

        arg_types = OrderedDict()
        optarg_types = OrderedDict()
        for param in signature.parameters.values():
            if param.kind not in (inspect.Parameter.POSITIONAL_ONLY,
                                  inspect.Parameter.POSITIONAL_OR_KEYWORD):
                # We pretend we don't see *args, kwpostargs=..., **kwargs.
                # Since every method can be still invoked without any arguments
                # going into *args and the slots after it, this is always safe,
                # if sometimes constraining.
                #
                # Accepting POSITIONAL_ONLY is OK, because the compiler
                # desugars the keyword arguments into positional ones internally.
                continue

            if param.default is inspect.Parameter.empty:
                arg_types[param.name] = self._type_of_param(function, loc, param,
                                                            is_syscall=syscall is not None)
            elif syscall is None:
                optarg_types[param.name] = self._type_of_param(function, loc, param,
                                                               is_syscall=syscall is not None)
            else:
                diag = diagnostic.Diagnostic("error",
                    "system call argument '{argument}' must not have a default value",
                    {"argument": param.name},
                    self._function_loc(function))
                self.engine.process(diag)

        if signature.return_annotation is not inspect.Signature.empty:
            ret_type = self._extract_annot(function, signature.return_annotation,
                                           "return type", loc, is_syscall=syscall is not None)
        elif syscall is None:
            diag = diagnostic.Diagnostic("error",
                "function must have a return type annotation to be called remotely", {},
                self._function_loc(function))
            self.engine.process(diag)
            ret_type = types.TVar()
        else: # syscall is not None
            diag = diagnostic.Diagnostic("error",
                "system call must have a return type annotation", {},
                self._function_loc(function))
            self.engine.process(diag)
            ret_type = types.TVar()

        if syscall is None:
            function_type = types.TRPCFunction(arg_types, optarg_types, ret_type,
                                               service=self._map(function))
            function_name = "__rpc_{}__".format(function_type.service)
        else:
            function_type = types.TCFunction(arg_types, ret_type,
                                             name=syscall)
            function_name = "__ffi_{}__".format(function_type.name)

        self.globals[function_name] = function_type
        self.functions[function] = function_name

        return function_name

    def _quote_function(self, function, loc):
        if function in self.functions:
            return self.functions[function]

        if hasattr(function, "artiq_embedded"):
            if function.artiq_embedded.function is not None:
                # Insert the typed AST for the new function and restart inference.
                # It doesn't really matter where we insert as long as it is before
                # the final call.
                function_node = self._quote_embedded_function(function)
                self.typedtree.insert(0, function_node)
                self.inference_finished = False
                return function_node.name
            elif function.artiq_embedded.syscall is not None:
                # Insert a storage-less global whose type instructs the compiler
                # to perform a system call instead of a regular call.
                return self._quote_foreign_function(function, loc,
                                                    syscall=function.artiq_embedded.syscall)
            else:
                assert False
        else:
            # Insert a storage-less global whose type instructs the compiler
            # to perform an RPC instead of a regular call.
            return self._quote_foreign_function(function, loc,
                                                syscall=None)

    def stitch_call(self, function, args, kwargs):
        function_node = self._quote_embedded_function(function)
        self.typedtree.append(function_node)

        # We synthesize source code for the initial call so that
        # diagnostics would have something meaningful to display to the user.
        synthesizer = ASTSynthesizer()
        call_node = synthesizer.call(function_node, args, kwargs)
        synthesizer.finalize()
        self.typedtree.append(call_node)

    def finalize(self):
        inferencer = Inferencer(engine=self.engine)

        # Iterate inference to fixed point.
        self.inference_finished = False
        while not self.inference_finished:
            self.inference_finished = True
            inferencer.visit(self.typedtree)

        # After we have found all functions, synthesize a module to hold them.
        source_buffer = source.Buffer("", "<synthesized>")
        self.typedtree = asttyped.ModuleT(
            typing_env=self.globals, globals_in_scope=set(),
            body=self.typedtree, loc=source.Range(source_buffer, 0, 0))
