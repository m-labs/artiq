"""
:class:`IntMonomorphizer` collapses the integer literals of undetermined
width to 32 bits, assuming they fit into 32 bits, or 64 bits if they
do not.
"""

from pythonparser import algorithm, diagnostic
from .. import types, builtins, asttyped

class IntMonomorphizer(algorithm.Visitor):
    def __init__(self, engine):
        self.engine = engine

    def visit_NumT(self, node):
        if builtins.is_int(node.type):
            if types.is_var(node.type["width"]):
                if -2**31 < node.n < 2**31-1:
                    width = 32
                elif -2**63 < node.n < 2**63-1:
                    width = 64
                else:
                    diag = diagnostic.Diagnostic("error",
                        "integer literal out of range for a signed 64-bit value", {},
                        node.loc)
                    self.engine.process(diag)
                    return

                node.type["width"].unify(types.TValue(width))
