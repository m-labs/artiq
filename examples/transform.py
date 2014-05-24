import inspect, textwrap, ast

from artiq import units, unparse

_now = "_ARTIQ_now"

class _RequestTransformer(ast.NodeTransformer):
	def __init__(self, target_globals):
		self.target_globals = target_globals

	def visit_FunctionDef(self, node):
		self.generic_visit(node)
		node.body.insert(0, ast.copy_location(
			ast.Assign(targets=[ast.Name(id=_now, ctx=ast.Store())],
				value=ast.Num(n=0)), node))
		node.body.append(ast.copy_location(
			ast.Return(value=ast.Name(id=_now, ctx=ast.Store())),
			node))
		return node

	def visit_Return(self, node):
		raise TypeError("Kernels cannot return values")

	def visit_Call(self, node):
		self.generic_visit(node)
		name = node.func.id
		if name == "delay":
			if len(node.args) != 1:
				raise TypeError("delay() takes 1 positional argument but {} were given".format(len(node.args)))
			return ast.copy_location(ast.AugAssign(
				target=ast.Name(id=_now, ctx=ast.Store()),
				op=ast.Add(), value=node.args[0]), node)
		return node

	def visit_Name(self, node):
		if not isinstance(node.ctx, ast.Load):
			return node
		try:
			obj = self.target_globals[node.id]
		except KeyError:
			return node
		if isinstance(obj, units.Quantity):
			return ast.Num(obj.amount)
		else:
			return node

def request_transform(target_ast, target_globals):
	transformer = _RequestTransformer(target_globals)
	transformer.visit(target_ast)

if __name__ == "__main__":
	import threads_test
	kernel = threads_test.threads_test
	a = ast.parse(textwrap.dedent(inspect.getsource(kernel)))
	request_transform(a, kernel.__globals__)
	unparse.Unparser(a)
