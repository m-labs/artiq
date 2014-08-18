import ast, operator

from artiq.compiler.tools import *

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
			operand = eval_constant(node.operand)
		except NotConstant:
			return node
		try:
			op = _ast_unops[type(node.op)]
		except KeyError:
			return node
		try:
			result = value_to_ast(op(operand))
		except:
			return node
		return ast.copy_location(result, node)

	def visit_BinOp(self, node):
		self.generic_visit(node)
		try:
			left, right = eval_constant(node.left), eval_constant(node.right)
		except NotConstant:
			return node
		try:
			op = _ast_binops[type(node.op)]
		except KeyError:
			return node
		try:
			result = value_to_ast(op(left, right))
		except:
			return node
		return ast.copy_location(result, node)

def fold_constants(node):
	_ConstantFolder().visit(node)
