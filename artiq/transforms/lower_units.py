import ast
from collections import defaultdict
from copy import copy

from artiq.language import units
from artiq.transforms.tools import embeddable_func_names


def _add_units(f, unit_list):
    def wrapper(*args):
        new_args = []
        for arg, unit in zip(args, unit_list):
            if unit is None:
                new_args.append(arg)
            else:
                if isinstance(arg, list):
                    new_args.append([units.Quantity(x, unit) for x in arg])
                else:
                    new_args.append(units.Quantity(arg, unit))
        return f(*new_args)
    return wrapper


class _UnitsLowerer(ast.NodeTransformer):
    def __init__(self, rpc_map):
        self.rpc_map = rpc_map
        # (original rpc number, (unit list)) -> new rpc number
        self.rpc_remap = defaultdict(lambda: len(self.rpc_remap))
        self.variable_units = dict()

    def visit_Name(self, node):
        try:
            unit = self.variable_units[node.id]
        except KeyError:
            pass
        else:
            if unit is not None:
                node.unit = unit
        return node

    def visit_BoolOp(self, node):
        self.generic_visit(node)
        us = [getattr(value, "unit", None) for value in node.values]
        if not all(u == us[0] for u in us[1:]):
            raise units.DimensionError
        return node

    def visit_Compare(self, node):
        self.generic_visit(node)
        u0 = getattr(node.left, "unit", None)
        us = [getattr(comparator, "unit", None)
              for comparator in node.comparators]
        if not all(u == u0 for u in us):
            raise units.DimensionError
        return node

    def visit_UnaryOp(self, node):
        self.generic_visit(node)
        if hasattr(node.operand, "unit"):
            node.unit = node.operand.unit
        return node

    def visit_BinOp(self, node):
        self.generic_visit(node)
        op = type(node.op)
        left_unit = getattr(node.left, "unit", None)
        right_unit = getattr(node.right, "unit", None)
        if op in (ast.Add, ast.Sub, ast.Mod):
            unit = units.addsub_dimension(left_unit, right_unit)
        elif op == ast.Mult:
            unit = units.mul_dimension(left_unit, right_unit)
        elif op in (ast.Div, ast.FloorDiv):
            unit = units.div_dimension(left_unit, right_unit)
        else:
            if left_unit is not None or right_unit is not None:
                raise units.DimensionError
            unit = None
        if unit is not None:
            node.unit = unit
        return node

    def visit_Attribute(self, node):
        self.generic_visit(node)
        if node.attr == "amount" and hasattr(node.value, "unit"):
            del node.value.unit
            return node.value
        else:
            return node

    def visit_List(self, node):
        self.generic_visit(node)
        if node.elts:
            us = [getattr(elt, "unit", None) for elt in node.elts]
            if not all(u == us[0] for u in us[1:]):
                raise units.DimensionError
            node.unit = us[0]
        return node

    def visit_ListComp(self, node):
        self.generic_visit(node)
        if hasattr(node.elt, "unit"):
            node.unit = node.elt.unit
        return node

    def visit_Call(self, node):
        self.generic_visit(node)
        if node.func.id == "Quantity":
            amount, unit = node.args
            amount.unit = unit.s
            return amount
        elif node.func.id in ("now", "cycles_to_time"):
            node.unit = "s"
        elif node.func.id == "syscall":
            # only RPCs can have units
            if node.args[0].s == "rpc":
                unit_list = tuple(getattr(arg, "unit", None)
                                  for arg in node.args[2:])
                rpc_n = node.args[1].n
                node.args[1].n = self.rpc_remap[(rpc_n, (unit_list))]
            else:
                if any(hasattr(arg, "unit") for arg in node.args):
                    raise units.DimensionError
        elif node.func.id in ("delay", "at", "time_to_cycles", "watchdog"):
            if getattr(node.args[0], "unit", None) != "s":
                raise units.DimensionError
        elif node.func.id == "check_unit":
            self.generic_visit(node)
        elif node.func.id in embeddable_func_names:
            # must be last (some embeddable funcs may have units)
            if any(hasattr(arg, "unit") for arg in node.args):
                raise units.DimensionError
        return node

    def visit_Expr(self, node):
        self.generic_visit(node)
        if (isinstance(node.value, ast.Call)
                and node.value.func.id == "check_unit"):
            call = node.value
            if (isinstance(call.args[1], ast.NameConstant)
                    and call.args[1].value is None):
                if hasattr(call.value.args[0], "unit"):
                    raise units.DimensionError
            elif isinstance(call.args[1], ast.Str):
                if getattr(call.args[0], "unit", None) != call.args[1].s:
                    raise units.DimensionError
            else:
                raise NotImplementedError
            return None
        else:
            return node

    def _update_target(self, target, unit):
        if isinstance(target, ast.Name):
            if target.id in self.variable_units:
                if self.variable_units[target.id] != unit:
                    raise TypeError(
                        "Inconsistent units for variable '{}': '{}' and '{}'"
                        .format(target.id,
                                self.variable_units[target.id],
                                unit))
            else:
                self.variable_units[target.id] = unit

    def visit_Assign(self, node):
        node.value = self.visit(node.value)
        unit = getattr(node.value, "unit", None)
        for target in node.targets:
            self._update_target(target, unit)
        return node

    def visit_AugAssign(self, node):
        value = self.visit_BinOp(ast.BinOp(
            op=node.op, left=node.target, right=node.value))
        unit = getattr(value, "unit", None)
        self._update_target(node.target, unit)
        return node

    # Only dimensionless iterators are supported
    def visit_For(self, node):
        self.generic_visit(node)
        self._update_target(node.target, None)
        return node


def lower_units(func_def, rpc_map):
    ul = _UnitsLowerer(rpc_map)
    ul.visit(func_def)
    original_map = copy(rpc_map)
    for (original_rpcn, unit_list), new_rpcn in ul.rpc_remap.items():
        rpc_map[new_rpcn] = _add_units(original_map[original_rpcn], unit_list)
