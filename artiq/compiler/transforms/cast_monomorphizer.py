"""
:class:`CastMonomorphizer` uses explicit casts to monomorphize
expressions of undetermined integer type to either 32 or 64 bits.
"""

from pythonparser import algorithm, diagnostic
from .. import types, builtins, asttyped

class CastMonomorphizer(algorithm.Visitor):
    def __init__(self, engine):
        self.engine = engine

    def visit_CallT(self, node):
        self.generic_visit(node)

        if (types.is_builtin(node.func.type, "int") or
                types.is_builtin(node.func.type, "int32") or
                types.is_builtin(node.func.type, "int64")):
            typ = node.type.find()
            if (not types.is_var(typ["width"]) and
                    builtins.is_int(node.args[0].type) and
                    types.is_var(node.args[0].type.find()["width"])):
                if isinstance(node.args[0], asttyped.BinOpT):
                    # Binary operations are a bit special: they can widen, and so their
                    # return type is indeterminate until both argument types are fully known.
                    # In case we first monomorphize the return type, and then some argument type,
                    # and argument type is wider than return type, we'll introduce a conflict.
                    return

                node.args[0].type.unify(typ)

