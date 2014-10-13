import ast

from artiq.transforms.tools import value_to_ast
from artiq.language.core import int64


def _time_to_cycles(ref_period, node):
    divided = ast.copy_location(
        ast.BinOp(left=node,
                  op=ast.Div(),
                  right=value_to_ast(ref_period)),
        node)
    return ast.copy_location(
        ast.Call(func=ast.Name("round64", ast.Load()),
                 args=[divided],
                 keywords=[], starargs=[], kwargs=[]),
        divided)


def _time_to_cycles_opt(ref_period, node):
    if (isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "cycles_to_time"):
        return node.args[0]
    else:
        return _time_to_cycles(ref_period, node)


def _cycles_to_time(ref_period, node):
    return ast.copy_location(
        ast.BinOp(left=node,
                  op=ast.Mult(),
                  right=value_to_ast(ref_period)),
        node)


class _TimeLowerer(ast.NodeTransformer):
    def __init__(self, ref_period):
        self.ref_period = ref_period

    def visit_Call(self, node):
        # optimize time_to_cycles(now()) -> now
        if (isinstance(node.func, ast.Name)
                and node.func.id == "time_to_cycles"
                and isinstance(node.args[0], ast.Call)
                and isinstance(node.args[0].func, ast.Name)
                and node.args[0].func.id == "now"):
            return ast.copy_location(ast.Name("now", ast.Load()), node)

        self.generic_visit(node)
        if isinstance(node.func, ast.Name):
            funcname = node.func.id
            if funcname == "now":
                return _cycles_to_time(
                    self.ref_period, 
                    ast.copy_location(ast.Name("now", ast.Load()), node))
            elif funcname == "time_to_cycles":
                return _time_to_cycles(self.ref_period, node.args[0])
            elif funcname == "cycles_to_time":
                return _cycles_to_time(self.ref_period, node.args[0])
        return node

    def visit_Expr(self, node):
        r = node
        if (isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name)):
            funcname = node.value.func.id
            if funcname == "delay":
                r = ast.copy_location(
                    ast.AugAssign(target=ast.Name("now", ast.Store()),
                                  op=ast.Add(),
                                  value=_time_to_cycles_opt(
                                    self.ref_period,
                                    node.value.args[0])),
                    node)
            elif funcname == "at":
                r = ast.copy_location(
                    ast.Assign(targets=[ast.Name("now", ast.Store())],
                               value=_time_to_cycles_opt(
                                    self.ref_period,
                                    node.value.args[0])),
                    node)
        self.generic_visit(r)
        return r


def lower_time(func_def, initial_time, ref_period):
    _TimeLowerer(ref_period).visit(func_def)
    func_def.body.insert(0, ast.copy_location(
        ast.Assign(targets=[ast.Name("now", ast.Store())],
                   value=value_to_ast(int64(initial_time))),
        func_def))
