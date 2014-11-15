"""This transform turns calls to delay/now/at that use non-integer time
expressed in seconds into calls that use int64 time expressed in multiples of
ref_period.

It does so by inserting multiplication/division/rounding operations around
those calls.

The time_to_cycles and cycles_to_time core language functions are also
implemented here.

"""

import ast

from artiq.transforms.tools import value_to_ast


def _call_now(node):
    return ast.copy_location(
        ast.Call(func=ast.Name("now", ast.Load()),
                 args=[], keywords=[], starargs=[], kwargs=[]),
        node)


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


def _cycles_to_time(ref_period, node):
    return ast.copy_location(
        ast.BinOp(left=node,
                  op=ast.Mult(),
                  right=value_to_ast(ref_period)),
        node)


class _TimeQuantizer(ast.NodeTransformer):
    def __init__(self, ref_period):
        self.ref_period = ref_period

    def visit_Call(self, node):
        funcname = node.func.id
        if funcname == "now":
            return _cycles_to_time(self.ref_period, _call_now(node))
        elif funcname == "delay" or funcname == "at":
            if (isinstance(node.args[0], ast.Call)
                    and node.args[0].func.id == "cycles_to_time"):
                # optimize:
                # delay/at(cycles_to_time(x)) -> delay/at(x)
                node.args[0] = self.visit(node.args[0].args[0])
            else:
                node.args[0] = _time_to_cycles(self.ref_period,
                                               self.visit(node.args[0]))
            return node
        elif funcname == "time_to_cycles":
            if (isinstance(node.args[0], ast.Call)
                    and node.args[0].func.id == "now"):
                # optimize:
                # time_to_cycles(now()) -> now()
                return _call_now(node)
            else:
                return _time_to_cycles(self.ref_period,
                                       self.visit(node.args[0]))
        elif funcname == "cycles_to_time":
            return _cycles_to_time(self.ref_period,
                                   self.visit(node.args[0]))
        else:
            self.generic_visit(node)
            return node


def quantize_time(func_def, ref_period):
    _TimeQuantizer(ref_period).visit(func_def)
