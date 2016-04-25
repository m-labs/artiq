"""
:class:`MonomorphismValidator` verifies that all type variables have been
elided, which is necessary for code generation.
"""

from pythonparser import algorithm, diagnostic
from .. import asttyped, types, builtins

class MonomorphismValidator(algorithm.Visitor):
    def __init__(self, engine):
        self.engine = engine

    def visit_FunctionDefT(self, node):
        super().generic_visit(node)

        return_type = node.signature_type.find().ret
        if types.is_polymorphic(return_type):
            note = diagnostic.Diagnostic("note",
                "the function has return type {type}",
                {"type": types.TypePrinter().name(return_type)},
                node.name_loc)
            diag = diagnostic.Diagnostic("error",
                "the return type of this function cannot be fully inferred", {},
                node.name_loc, notes=[note])
            self.engine.process(diag)

    visit_QuotedFunctionDefT = visit_FunctionDefT

    def generic_visit(self, node):
        super().generic_visit(node)

        if isinstance(node, asttyped.commontyped):
            if types.is_polymorphic(node.type):
                note = diagnostic.Diagnostic("note",
                    "the expression has type {type}",
                    {"type": types.TypePrinter().name(node.type)},
                    node.loc)
                diag = diagnostic.Diagnostic("error",
                    "the type of this expression cannot be fully inferred", {},
                    node.loc, notes=[note])
                self.engine.process(diag)
