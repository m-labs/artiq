import ast

from artiq.transforms.tools import value_to_ast
from artiq.language import units


# TODO:
#  * track variable and expression dimensions
#  * raise exception on dimension errors in expressions
#  * modify RPC map to reintroduce units
#  * handle core time conversion outside of delay/at,
#    e.g. foo = now() + 1*us [...] at(foo)

class _UnitsLowerer(ast.NodeTransformer):
    def __init__(self, ref_period):
        self.ref_period = ref_period
        self.in_core_time = False

    def visit_Call(self, node):
        fn = node.func.id
        if fn in ("delay", "at"):
            old_in_core_time = self.in_core_time
            self.in_core_time = True
            self.generic_visit(node)
            self.in_core_time = old_in_core_time
        elif fn == "Quantity":
            if self.in_core_time:
                if node.args[1].id == "microcycle_units":
                    node = node.args[0]
                else:
                    node = ast.copy_location(
                        ast.BinOp(left=node.args[0],
                                  op=ast.Div(),
                                  right=value_to_ast(self.ref_period)),
                        node)
            else:
                node = node.args[0]
        else:
            self.generic_visit(node)
        return node


def lower_units(funcdef, ref_period):
    if (not isinstance(ref_period, units.Quantity)
            or ref_period.unit is not units.s_unit):
        raise units.DimensionError("Reference period not expressed in seconds")
    _UnitsLowerer(ref_period.amount).visit(funcdef)
