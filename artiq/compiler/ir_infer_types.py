import ast
from operator import itemgetter
from copy import deepcopy

from artiq.compiler.ir_ast_body import Visitor

class _TypeScanner(ast.NodeVisitor):
	def __init__(self, ns):
		self.exprv = Visitor(ns)

	def visit_Assign(self, node):
		val = self.exprv.visit_expression(node.value)
		ns = self.exprv.ns
		for target in node.targets:
			if isinstance(target, ast.Name):
				if target.id in ns:
					ns[target.id].merge(val)
				else:
					ns[target.id] = val
			else:
				raise NotImplementedError

	def visit_AugAssign(self, node):
		val = self.exprv.visit_expression(ast.BinOp(op=node.op, left=node.target, right=node.value))
		ns = self.exprv.ns
		target = node.target
		if isinstance(target, ast.Name):
			if target.id in ns:
				ns[target.id].merge(val)
			else:
				ns[target.id] = val
		else:
			raise NotImplementedError

def infer_types(node):
	ns = dict()
	while True:
		prev_ns = deepcopy(ns)
		ts = _TypeScanner(ns)
		ts.visit(node)
		if prev_ns and all(v.same_type(prev_ns[k]) for k, v in ns.items()):
			# no more promotions - completed
			return ns

if __name__ == "__main__":
	testcode = """
a = 2          # promoted later to int64
b = a + 1      # initially int32, becomes int64 after a is promoted
c = b//2       # initially int32, becomes int64 after b is promoted
d = 4          # stays int32
x = int64(7)
a += x         # promotes a to int64
foo = True
"""
	ns = infer_types(ast.parse(testcode))
	for k, v in sorted(ns.items(), key=itemgetter(0)):
		print("{:10}-->   {}".format(k, str(v)))
