import ast
from copy import deepcopy

from artiq.transforms.tools import eval_ast, value_to_ast


def _count_stmts(node):
    if isinstance(node, list):
        return sum(map(_count_stmts, node))
    elif isinstance(node, ast.With):
        return 1 + _count_stmts(node.body)
    elif isinstance(node, (ast.For, ast.While, ast.If)):
        return 1 + _count_stmts(node.body) + _count_stmts(node.orelse)
    elif isinstance(node, ast.Try):
        r = 1 + _count_stmts(node.body) \
            + _count_stmts(node.orelse) \
            + _count_stmts(node.finalbody)
        for handler in node.handlers:
            r += 1 + _count_stmts(handler.body)
        return r
    else:
        return 1


def _loop_breakable(node):
    if isinstance(node, list):
        return any(map(_loop_breakable, node))
    elif isinstance(node, (ast.Break, ast.Continue)):
        return True
    elif isinstance(node, ast.With):
        return _loop_breakable(node.body)
    elif isinstance(node, ast.If):
        return _loop_breakable(node.body) or _loop_breakable(node.orelse)
    elif isinstance(node, ast.Try):
        if (_loop_breakable(node.body)
                or _loop_breakable(node.orelse)
                or _loop_breakable(node.finalbody)):
            return True
        for handler in node.handlers:
            if _loop_breakable(handler.body):
                return True
        return False
    else:
        return False


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
                    replacement += deepcopy(node.body)
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
