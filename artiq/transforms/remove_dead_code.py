import ast

from artiq.transforms.tools import is_replaceable


class _SourceLister(ast.NodeVisitor):
    def __init__(self):
        self.sources = set()

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self.sources.add(node.id)


class _DeadCodeRemover(ast.NodeTransformer):
    def __init__(self, kept_targets):
        self.kept_targets = kept_targets

    def visit_Assign(self, node):
        new_targets = []
        for target in node.targets:
            if not (isinstance(target, ast.Name)
                    and target.id not in self.kept_targets):
                new_targets.append(target)
        if not new_targets and is_replaceable(node.value):
            return None
        else:
            return node

    def visit_AugAssign(self, node):
        if (isinstance(node.target, ast.Name)
                and node.target.id not in self.kept_targets
                and is_replaceable(node.value)):
            return None
        else:
            return node

    def visit_If(self, node):
        if isinstance(node.test, ast.NameConstant):
            if node.test.value:
                return node.body
            else:
                return node.orelse
        else:
            return node

    def visit_While(self, node):
        if isinstance(node.test, ast.NameConstant) and not node.test.value:
            return node.orelse
        else:
            return node


def remove_dead_code(func_def):
    sl = _SourceLister()
    sl.visit(func_def)
    _DeadCodeRemover(sl.sources).visit(func_def)
