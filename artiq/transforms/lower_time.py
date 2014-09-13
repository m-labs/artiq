import ast

from artiq.transforms.tools import value_to_ast
from artiq.language.core import int64


def _insert_int64(node):
    return ast.copy_location(
        ast.Call(func=ast.Name("int64", ast.Load()),
                 args=[node],
                 keywords=[], starargs=[], kwargs=[]),
        node)


class _TimeLowerer(ast.NodeTransformer):
    def visit_Call(self, node):
        if isinstance(node.func, ast.Name) and node.func.id == "now":
            return ast.copy_location(ast.Name("now", ast.Load()), node)
        else:
            self.generic_visit(node)
            return node

    def visit_Expr(self, node):
        self.generic_visit(node)
        if (isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name)):
            funcname = node.value.func.id
            if funcname == "delay":
                return ast.copy_location(
                    ast.AugAssign(target=ast.Name("now", ast.Store()),
                                  op=ast.Add(),
                                  value=_insert_int64(node.value.args[0])),
                    node)
            elif funcname == "at":
                return ast.copy_location(
                    ast.Assign(targets=[ast.Name("now", ast.Store())],
                               value=_insert_int64(node.value.args[0])),
                    node)
            else:
                return node
        else:
            return node


def lower_time(func_def, initial_time):
    _TimeLowerer().visit(func_def)
    func_def.body.insert(0, ast.copy_location(
        ast.Assign(targets=[ast.Name("now", ast.Store())],
                   value=value_to_ast(int64(initial_time))),
        func_def))
