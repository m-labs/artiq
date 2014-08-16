import ast
from operator import itemgetter
from copy import deepcopy

from artiq.compiler.ir_ast_body import ExpressionVisitor

class _Namespace:
	def __init__(self, name_to_value):
		self.name_to_value = name_to_value

	def load(self, builder, name):
		return self.name_to_value[name]

class _TypeScanner(ast.NodeVisitor):
	def __init__(self, namespace):
		self.exprv = ExpressionVisitor(None, namespace)

	def visit_Assign(self, node):
		val = self.exprv.visit(node.value)
		n2v = self.exprv.ns.name_to_value
		for target in node.targets:
			if isinstance(target, ast.Name):
				if target.id in n2v:
					n2v[target.id].merge(val)
				else:
					n2v[target.id] = val
			else:
				raise NotImplementedError

	def visit_AugAssign(self, node):
		val = self.exprv.visit(ast.BinOp(op=node.op, left=node.target, right=node.value))
		n2v = self.exprv.ns.name_to_value
		target = node.target
		if isinstance(target, ast.Name):
			if target.id in n2v:
				n2v[target.id].merge(val)
			else:
				n2v[target.id] = val
		else:
			raise NotImplementedError

def infer_types(node):
	name_to_value = dict()
	while True:
		prev_name_to_value = deepcopy(name_to_value)
		ns = _Namespace(name_to_value)
		ts = _TypeScanner(ns)
		ts.visit(node)
		if prev_name_to_value and all(v.same_type(prev_name_to_value[k]) for k, v in name_to_value.items()):
			# no more promotions - completed
			return name_to_value

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
	n2v = infer_types(ast.parse(testcode))
	for k, v in sorted(n2v.items(), key=itemgetter(0)):
		print("{:10}-->   {}".format(k, str(v)))
