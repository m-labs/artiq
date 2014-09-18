import ast

from artiq.transforms.tools import eval_ast, value_to_ast


def _count_stmts(node):
    if isinstance(node, (ast.For, ast.While, ast.If)):
        return 1 + _count_stmts(node.body) + _count_stmts(node.orelse)
    elif isinstance(node, ast.With):
        return 1 + _count_stmts(node.body)
    elif isinstance(node, list):
        return sum(map(_count_stmts, node))
    else:
        return 1


def _loop_breakable(node):
    if isinstance(node, ast.Break):
        return 1
    elif isinstance(node, ast.Return):
        return 2
    elif isinstance(node, list):
        return max(map(_loop_breakable, node), default=0)
    elif isinstance(node, ast.If):
        return max(_loop_breakable(node.body), _loop_breakable(node.orelse))
    elif isinstance(node, (ast.For, ast.While)):
        bb = _loop_breakable(node.body)
        if bb == 1:
            bb = 0
        return max(bb, _loop_breakable(node.orelse))
    else:
        return 0


class _LoopUnroller(ast.NodeTransformer):
    def __init__(self, limit):
        self.limit = limit

    def visit_For(self, node):
        self.generic_visit(node)
        try:
            it = eval_ast(node.iter)
        except:
            return node
        l_it = len(it)
        if l_it:
            if (not _loop_breakable(node.body)
                    and l_it*_count_stmts(node.body) < self.limit):
                replacement = []
                for i in it:
                    if not isinstance(i, int):
                        replacement = None
                        break
                    replacement.append(ast.copy_location(
                        ast.Assign(targets=[node.target],
                                   value=value_to_ast(i)),
                        node))
                    replacement += node.body
                if replacement is not None:
                    return replacement
                else:
                    return node
            else:
                return node
        else:
            return node.orelse


def unroll_loops(node, limit):
    _LoopUnroller(limit).visit(node)
