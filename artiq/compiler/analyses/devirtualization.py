"""
:class:`Devirtualizer` performs method resolution at
compile time.

Devirtualization is implemented using a lattice
with three states: unknown → assigned once → diverges.
The lattice is computed individually for every
variable in scope as well as every
(instance type, field name) pair.
"""

from pythonparser import algorithm
from .. import asttyped, ir, types

def _advance(target_map, key, value):
    if key not in target_map:
        target_map[key] = value # unknown → assigned once
    else:
        target_map[key] = None  # assigned once → diverges

class FunctionResolver(algorithm.Visitor):
    def __init__(self, variable_map):
        self.variable_map = variable_map

        self.scope_map = dict()
        self.queue = []

        self.in_assign = False
        self.current_scopes = []

    def finalize(self):
        for thunk in self.queue:
            thunk()

    def visit_scope(self, node):
        self.current_scopes.append(node)
        self.generic_visit(node)
        self.current_scopes.pop()

    def visit_in_assign(self, node):
        self.in_assign = True
        self.visit(node)
        self.in_assign = False

    def visit_Assign(self, node):
        self.visit(node.value)
        self.visit_in_assign(node.targets)

    def visit_ForT(self, node):
        self.visit(node.iter)
        self.visit_in_assign(node.target)
        self.visit(node.body)
        self.visit(node.orelse)

    def visit_withitemT(self, node):
        self.visit(node.context_expr)
        self.visit_in_assign(node.optional_vars)

    def visit_comprehension(self, node):
        self.visit(node.iter)
        self.visit_in_assign(node.target)
        self.visit(node.ifs)

    def visit_ModuleT(self, node):
        self.visit_scope(node)

    def visit_FunctionDefT(self, node):
        _advance(self.scope_map, (self.current_scopes[-1], node.name), node)
        self.visit_scope(node)

    def visit_NameT(self, node):
        if self.in_assign:
            # Just give up if we assign anything at all to a variable, and
            # assume it diverges.
            _advance(self.scope_map, (self.current_scopes[-1], node.id), None)
        else:
            # Look up the final value in scope_map and copy it into variable_map.
            keys = [(scope, node.id) for scope in reversed(self.current_scopes)]
            def thunk():
                for key in keys:
                    if key in self.scope_map:
                        self.variable_map[node] = self.scope_map[key]
                        return
            self.queue.append(thunk)

class MethodResolver(algorithm.Visitor):
    def __init__(self, variable_map, method_map):
        self.variable_map = variable_map
        self.method_map = method_map

    # embedding.Stitcher.finalize generates initialization statements
    # of form "constructor.meth = meth_body".
    def visit_Assign(self, node):
        if node.value not in self.variable_map:
            return

        value = self.variable_map[node.value]
        for target in node.targets:
            if isinstance(target, asttyped.AttributeT):
                if types.is_constructor(target.value.type):
                    instance_type = target.value.type.instance
                elif types.is_instance(target.value.type):
                    instance_type = target.value.type
                else:
                    continue
                _advance(self.method_map, (instance_type, target.attr), value)

class Devirtualization:
    def __init__(self):
        self.variable_map = dict()
        self.method_map = dict()

    def visit(self, node):
        function_resolver = FunctionResolver(self.variable_map)
        function_resolver.visit(node)
        function_resolver.finalize()

        method_resolver = MethodResolver(self.variable_map, self.method_map)
        method_resolver.visit(node)
