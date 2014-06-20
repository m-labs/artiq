import ast, operator

from artiq.language import units
from artiq.compiler.tools import value_to_ast, make_stmt_transformer

class _NotConstant(Exception):
	pass

def _get_constant(node):
	if isinstance(node, ast.Num):
		return node.n
	elif isinstance(node, ast.Str):
		return node.s
	elif isinstance(node, ast.Call) \
	  and isinstance(node.func, ast.Name) \
	  and node.func.id == "Quantity":
		amount, unit = node.args
		amount = _get_constant(amount)
		try:
			unit = getattr(units, unit.id)
		except:
			raise _NotConstant
		return units.Quantity(amount, unit)
	else:
		raise _NotConstant

_ast_unops = {
	ast.Invert: operator.inv,
	ast.Not: operator.not_,
	ast.UAdd: operator.pos,
	ast.USub: operator.neg
}

_ast_binops = {
	ast.Add: operator.add,
	ast.Sub: operator.sub,
	ast.Mult: operator.mul,
	ast.Div: operator.truediv,
	ast.FloorDiv: operator.floordiv,
	ast.Mod: operator.mod,
	ast.Pow: operator.pow,
	ast.LShift: operator.lshift,
	ast.RShift: operator.rshift,
	ast.BitOr: operator.or_,
	ast.BitXor: operator.xor,
	ast.BitAnd: operator.and_
}

class _ConstantFolder(ast.NodeTransformer):
	def visit_UnaryOp(self, node):
		self.generic_visit(node)
		try:
			operand = _get_constant(node.operand)
		except _NotConstant:
			return node
		try:
			op = _ast_unops[type(node.op)]
		except KeyError:
			return node
		try:
			result = value_to_ast(op(operand))
		except:
			return node
		return result

	def visit_BinOp(self, node):
		self.generic_visit(node)
		try:
			left, right = _get_constant(node.left), _get_constant(node.right)
		except _NotConstant:
			return node
		try:
			op = _ast_binops[type(node.op)]
		except KeyError:
			return node
		try:
			result = value_to_ast(op(left, right))
		except:
			return node
		return result

fold_constants = make_stmt_transformer(_ConstantFolder)
