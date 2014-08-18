import ast
from artiq.compiler.tools import value_to_ast

class _TimeLowerer(ast.NodeTransformer):
	def __init__(self, ref_period):
		self.ref_period = ref_period

	def visit_Call(self, node):
		if isinstance(node.func, ast.Name) \
		  and node.func.id == "Quantity" and node.args[1].id == "s_unit":
			return ast.copy_location(
				ast.BinOp(left=node.args[0], op=ast.Div(), right=value_to_ast(self.ref_period.amount)),
				node)
		elif isinstance(node.func, ast.Name) and node.func.id == "now":
			return ast.copy_location(ast.Name("now", ast.Load()), node)
		else:
			self.generic_visit(node)
			return node

	def visit_Expr(self, node):
		self.generic_visit(node)
		if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name):
			funcname = node.value.func.id
			if funcname == "delay":
				return ast.copy_location(
					ast.AugAssign(target=ast.Name("now", ast.Store()), op=ast.Add(), value=node.value.args[0]),
					node)
			elif funcname == "at":
				return ast.copy_location(
					ast.Assign(targets=[ast.Name("now", ast.Store())], value=node.value.args[0]),
					node)
			else:
				return node
		else:
			return node

def lower_time(funcdef, initial_time):
	_TimeLowerer().visit(funcdef)
	funcdef.body.insert(0, ast.copy_location(
		ast.Assign(targets=[ast.Name("now", ast.Store())], value=value_to_ast(initial_time)),
		funcdef))
