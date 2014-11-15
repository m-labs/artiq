"""This transform implements time management functions (delay/now/at)
using an accumulator 'now' and simple replacement rules:

    delay(t) ->  now += t
    now()    ->  now
    at(t)    ->  now = t

Time parameters must be quantized to integers before running this transform.
The accumulator is initialized to an int64 value at the beginning of the
output function.

"""

import ast

from artiq.transforms.tools import value_to_ast
from artiq.language.core import int64


class _TimeLowerer(ast.NodeTransformer):
    def visit_Call(self, node):
        if node.func.id == "now":
            return ast.copy_location(ast.Name("now", ast.Load()), node)
        else:
            self.generic_visit(node)
            return node

    def visit_Expr(self, node):
        r = node
        if isinstance(node.value, ast.Call):
            funcname = node.value.func.id
            if funcname == "delay":
                r = ast.copy_location(
                    ast.AugAssign(target=ast.Name("now", ast.Store()),
                                  op=ast.Add(),
                                  value=node.value.args[0]),
                    node)
            elif funcname == "at":
                r = ast.copy_location(
                    ast.Assign(targets=[ast.Name("now", ast.Store())],
                               value=node.value.args[0]),
                    node)
        self.generic_visit(r)
        return r


def lower_time(func_def, initial_time):
    _TimeLowerer().visit(func_def)
    func_def.body.insert(0, ast.copy_location(
        ast.Assign(targets=[ast.Name("now", ast.Store())],
                   value=value_to_ast(int64(initial_time))),
        func_def))
