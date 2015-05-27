import pythonparser.algorithm
from pythonparser import ast
from copy import deepcopy

from artiq.py2llvm.ast_body import Visitor
from artiq.py2llvm import base_types


class _TypeScanner(pythonparser.algorithm.Visitor):
    def __init__(self, env, ns):
        self.exprv = Visitor(env, ns)

    def _update_target(self, target, val):
        ns = self.exprv.ns
        if isinstance(target, ast.Name):
            if target.id in ns:
                ns[target.id].merge(val)
            else:
                ns[target.id] = deepcopy(val)
        elif isinstance(target, ast.Subscript):
            target = target.value
            levels = 0
            while isinstance(target, ast.Subscript):
                target = target.value
                levels += 1
            if isinstance(target, ast.Name):
                target_value = ns[target.id]
                for i in range(levels):
                    target_value = target_value.o_subscript(None, None)
                target_value.merge_subscript(val)
            else:
                raise NotImplementedError
        else:
            raise NotImplementedError

    def visit_Assign(self, node):
        val = self.exprv.visit_expression(node.value)
        for target in node.targets:
            self._update_target(target, val)

    def visit_AugAssign(self, node):
        val = self.exprv.visit_expression(ast.BinOp(
            op=node.op, left=node.target, right=node.value))
        self._update_target(node.target, val)

    def visit_For(self, node):
        it = self.exprv.visit_expression(node.iter)
        self._update_target(node.target, it.get_value_ptr())
        self.generic_visit(node)

    def visit_Return(self, node):
        if node.value is None:
            val = base_types.VNone()
        else:
            val = self.exprv.visit_expression(node.value)
        ns = self.exprv.ns
        if "return" in ns:
            ns["return"].merge(val)
        else:
            ns["return"] = deepcopy(val)


def infer_function_types(env, node, param_types):
    ns = deepcopy(param_types)
    ts = _TypeScanner(env, ns)
    ts.visit(node)
    while True:
        prev_ns = deepcopy(ns)
        ts = _TypeScanner(env, ns)
        ts.visit(node)
        if all(v.same_type(prev_ns[k]) for k, v in ns.items()):
            # no more promotions - completed
            if "return" not in ns:
                ns["return"] = base_types.VNone()
            return ns
