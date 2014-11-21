import ast

from artiq.language import units


def _add_units(f, unit_list):
    def wrapper(*args):
        new_args = [arg if unit is None else units.Quantity(arg, unit)
                    for arg, unit in zip(args, unit_list)]
        return f(*new_args)
    return wrapper


class _UnitsLowerer(ast.NodeTransformer):
    def __init__(self, rpc_map):
        self.rpc_map = rpc_map
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

    def visit_Call(self, node):
        self.generic_visit(node)
        if node.func.id == "Quantity":
            amount, unit = node.args
            amount.unit = unit.s
            return amount
        elif node.func.id == "now":
            node.unit = "s"
        elif node.func.id == "syscall" and node.args[0].s == "rpc":
            unit_list = [getattr(arg, "unit", None) for arg in node.args]
            rpc_n = node.args[1].n
            self.rpc_map[rpc_n] = _add_units(self.rpc_map[rpc_n], unit_list)
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
    _UnitsLowerer(rpc_map).visit(func_def)
