"""
:class:`Devirtualizer` performs method resolution at
compile time.

Devirtualization is implemented using a lattice
with three states: unknown → assigned once → diverges.
The lattice is computed individually for every
variable in scope as well as every
(constructor type, field name) pair.
"""

from pythonparser import algorithm
from .. import ir, types

def _advance(target_map, key, value):
    if key not in target_map:
        target_map[key] = value # unknown → assigned once
    else:
        target_map[key] = None  # assigned once → diverges

class FunctionResolver(algorithm.Visitor):
    def __init__(self, variable_map):
        self.variable_map = variable_map

        self.in_assign = False
        self.scope_map = dict()
        self.scope = None
        self.queue = []

    def finalize(self):
        for thunk in self.queue:
            thunk()

    def visit_scope(self, node):
        old_scope, self.scope = self.scope, node
        self.generic_visit(node)
        self.scope = old_scope

    def visit_in_assign(self, node):
        self.in_assign = True
        self.visit(node)
        self.in_assign = False

    def visit_Assign(self, node):
        self.visit(node.value)
        self.visit_in_assign(node.targets)

    def visit_For(self, node):
        self.visit(node.iter)
        self.visit_in_assign(node.target)
        self.visit(node.body)
        self.visit(node.orelse)

    def visit_withitem(self, node):
        self.visit(node.context_expr)
        self.visit_in_assign(node.optional_vars)

    def visit_comprehension(self, node):
        self.visit(node.iter)
        self.visit_in_assign(node.target)
        self.visit(node.ifs)

    def visit_ModuleT(self, node):
        self.visit_scope(node)

    def visit_FunctionDefT(self, node):
        _advance(self.scope_map, (self.scope, node.name), node)
        self.visit_scope(node)

    def visit_NameT(self, node):
        if self.in_assign:
            # Just give up if we assign anything at all to a variable, and
            # assume it diverges.
            _advance(self.scope_map, (self.scope, node.id), None)
        else:
            # Copy the final value in scope_map into variable_map.
            key = (self.scope, node.id)
            def thunk():
                if key in self.scope_map:
                    self.variable_map[node] = self.scope_map[key]
            self.queue.append(thunk)

class Devirtualizer:
    def __init__(self):
        self.variable_map = dict()
        self.method_map = dict()

    def visit(self, node):
        resolver = FunctionResolver(self.variable_map)
        resolver.visit(node)
        resolver.finalize()
        # print(self.variable_map)
