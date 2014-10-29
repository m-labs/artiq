import ast
from copy import copy, deepcopy

from artiq.transforms.tools import is_replaceable


class _TargetLister(ast.NodeVisitor):
    def __init__(self):
        self.targets = set()

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Store):
            self.targets.add(node.id)


class _InterAssignRemover(ast.NodeTransformer):
    def __init__(self):
        self.replacements = dict()
        self.modified_names = set()

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            try:
                return self.replacements[node.id]
            except KeyError:
                return node
        else:
            self.modified_names.add(node.id)
            return node

    def visit_Assign(self, node):
        self.generic_visit(node)
        if is_replaceable(node.value):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.replacements[target.id] = node.value
        else:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    try:
                        del self.replacements[target.id]
                    except KeyError:
                        pass
        return node

    def visit_AugAssign(self, node):
        left = deepcopy(node.target)
        left.ctx = ast.Load()
        newnode = ast.copy_location(
            ast.Assign(
                targets=[node.target],
                value=ast.BinOp(left=left, op=node.op, right=node.value)
            ),
            node
        )
        return self.visit_Assign(newnode)

    def modified_names_push(self):
        prev_modified_names = self.modified_names
        self.modified_names = set()
        return prev_modified_names

    def modified_names_pop(self, prev_modified_names):
        for name in self.modified_names:
            try:
                del self.replacements[name]
            except KeyError:
                pass
        self.modified_names |= prev_modified_names

    def visit_Try(self, node):
        prev_modified_names = self.modified_names_push()
        self.generic_visit(node)
        self.modified_names_pop(prev_modified_names)
        return node

    def visit_If(self, node):
        node.test = self.visit(node.test)

        prev_modified_names = self.modified_names_push()

        prev_replacements = self.replacements
        self.replacements = copy(prev_replacements)
        node.body = [self.visit(n) for n in node.body]
        self.replacements = copy(prev_replacements)
        node.orelse = [self.visit(n) for n in node.orelse]
        self.replacements = prev_replacements

        self.modified_names_pop(prev_modified_names)

        return node

    def visit_loop(self, node):
        prev_modified_names = self.modified_names_push()
        prev_replacements = self.replacements

        self.replacements = copy(prev_replacements)
        tl = _TargetLister()
        for n in node.body:
            tl.visit(n)
        for name in tl.targets:
            try:
                del self.replacements[name]
            except KeyError:
                pass
        node.body = [self.visit(n) for n in node.body]

        self.replacements = copy(prev_replacements)
        node.orelse = [self.visit(n) for n in node.orelse]

        self.replacements = prev_replacements
        self.modified_names_pop(prev_modified_names)

    def visit_For(self, node):
        prev_modified_names = self.modified_names_push()
        node.target = self.visit(node.target)
        self.modified_names_pop(prev_modified_names)
        node.iter = self.visit(node.iter)
        self.visit_loop(node)
        return node

    def visit_While(self, node):
        self.visit_loop(node)
        node.test = self.visit(node.test)
        return node


def remove_inter_assigns(func_def):
    _InterAssignRemover().visit(func_def)
