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
        if (types.is_builtin(node.func.type, "int") or
                types.is_builtin(node.func.type, "int32") or
                types.is_builtin(node.func.type, "int64")):
            typ = node.type.find()
            if (not types.is_var(typ["width"]) and
                    len(node.args) == 1 and
                    builtins.is_int(node.args[0].type) and
                    types.is_var(node.args[0].type.find()["width"])):
                if isinstance(node.args[0], asttyped.BinOpT):
                    # Binary operations are a bit special: they can widen, and so their
                    # return type is indeterminate until both argument types are fully known.
                    # In case we first monomorphize the return type, and then some argument type,
                    # and argument type is wider than return type, we'll introduce a conflict.
                    return

                node.args[0].type.unify(typ)

        if types.is_builtin(node.func.type, "int") or \
                types.is_builtin(node.func.type, "round"):
            typ = node.type.find()
            if types.is_var(typ["width"]):
                typ["width"].unify(types.TValue(32))

        self.generic_visit(node)

    def visit_CoerceT(self, node):
        if isinstance(node.value, asttyped.NumT) and \
                builtins.is_int(node.type) and \
                builtins.is_int(node.value.type) and \
                not types.is_var(node.type["width"]) and \
                types.is_var(node.value.type["width"]):
            node.value.type.unify(node.type)

        self.generic_visit(node)
