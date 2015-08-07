"""
The :class:`Stitcher` class allows to transparently combine compiled
Python code and Python code executed on the host system: it resolves
the references to the host objects and translates the functions
annotated as ``@kernel`` when they are referenced.
"""

import inspect
from pythonparser import ast, source, diagnostic, parse_buffer
from . import types, builtins, asttyped, prelude
from .transforms import ASTTypedRewriter, Inferencer


class ASTSynthesizer:
    def __init__(self):
        self.source = ""
        self.source_buffer = source.Buffer(self.source, "<synthesized>")

    def finalize(self):
        self.source_buffer.source = self.source
        return self.source_buffer

    def _add(self, fragment):
        range_from   = len(self.source)
        self.source += fragment
        range_to     = len(self.source)
        return source.Range(self.source_buffer, range_from, range_to)

    def quote(self, value):
        """Construct an AST fragment equal to `value`."""
        if value in (None, True, False):
            if node.value is True or node.value is False:
                typ = builtins.TBool()
            elif node.value is None:
                typ = builtins.TNone()
            return asttyped.NameConstantT(value=value, type=typ,
                                          loc=self._add(repr(value)))
        elif isinstance(value, (int, float)):
            if isinstance(value, int):
                typ = builtins.TInt()
            elif isinstance(value, float):
                typ = builtins.TFloat()
            return asttyped.NumT(n=value, ctx=None, type=typ,
                                 loc=self._add(repr(value)))
        elif isinstance(value, list):
            begin_loc = self._add("[")
            elts = []
            for index, elt in value:
                elts.append(self.quote(elt))
                if index < len(value) - 1:
                    self._add(", ")
            end_loc   = self._add("]")
            return asttyped.ListT(elts=elts, ctx=None, type=types.TVar(),
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
    pass

class Stitcher:
    def __init__(self, engine=None):
        if engine is None:
            self.engine = diagnostic.Engine(all_errors_are_fatal=True)
        else:
            self.engine = engine

        self.asttyped_rewriter = StitchingASTTypedRewriter(
            engine=self.engine, globals=prelude.globals())
        self.inferencer = Inferencer(engine=self.engine)

        self.name = "stitched"
        self.typedtree = None
        self.globals = self.asttyped_rewriter.globals

        self.rpc_map = {}

    def _iterate(self):
        # Iterate inference to fixed point.
        self.inference_finished = False
        while not self.inference_finished:
            self.inference_finished = True
            self.inferencer.visit(self.typedtree)

    def _parse_embedded_function(self, function):
        if not hasattr(function, "artiq_embedded"):
            raise ValueError("{} is not an embedded function".format(repr(function)))

        # Extract function source.
        embedded_function = function.artiq_embedded.function
        source_code = inspect.getsource(embedded_function)
        filename = embedded_function.__code__.co_filename
        first_line = embedded_function.__code__.co_firstlineno

        # Parse.
        source_buffer = source.Buffer(source_code, filename, first_line)
        parsetree, comments = parse_buffer(source_buffer, engine=self.engine)

        # Rewrite into typed form.
        typedtree = self.asttyped_rewriter.visit(parsetree)

        return typedtree, typedtree.body[0]

    def stitch_call(self, function, args, kwargs):
        self.typedtree, function_node = self._parse_embedded_function(function)

        # We synthesize fake source code for the initial call so that
        # diagnostics would have something meaningful to display to the user.
        synthesizer = ASTSynthesizer()
        call_node = synthesizer.call(function_node, args, kwargs)
        synthesizer.finalize()
        self.typedtree.body.append(call_node)

        self._iterate()
