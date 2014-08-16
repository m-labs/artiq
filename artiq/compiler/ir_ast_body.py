import ast

from artiq.compiler import ir_values

_ast_unops = {
	ast.Invert: ir_values.operators.inv,
	ast.Not: ir_values.operators.not_,
	ast.UAdd: ir_values.operators.pos,
	ast.USub: ir_values.operators.neg
}

_ast_binops = {
	ast.Add: ir_values.operators.add,
	ast.Sub: ir_values.operators.sub,
	ast.Mult: ir_values.operators.mul,
	ast.Div: ir_values.operators.truediv,
	ast.FloorDiv: ir_values.operators.floordiv,
	ast.Mod: ir_values.operators.mod,
	ast.Pow: ir_values.operators.pow,
	ast.LShift: ir_values.operators.lshift,
	ast.RShift: ir_values.operators.rshift,
	ast.BitOr: ir_values.operators.or_,
	ast.BitXor: ir_values.operators.xor,
	ast.BitAnd: ir_values.operators.and_
}

_ast_cmps = {
	ast.Eq: ir_values.operators.eq,
	ast.NotEq: ir_values.operators.ne,
	ast.Lt: ir_values.operators.lt,
	ast.LtE: ir_values.operators.le,
	ast.Gt: ir_values.operators.gt,
	ast.GtE: ir_values.operators.ge
}

_ast_unfuns = {
	"bool": ir_values.operators.bool,
	"int": ir_values.operators.int,
	"int64": ir_values.operators.int64,
	"round": ir_values.operators.round,
	"round64": ir_values.operators.round64,
}

class ExpressionVisitor:
	def __init__(self, builder, ns):
		self.builder = builder
		self.ns = ns

	def visit(self, node):
		if isinstance(node, ast.Name):
			return self.ns.load(self.builder, node.id)
		elif isinstance(node, ast.NameConstant):
			v = node.value
			if isinstance(v, bool):
				r = ir_values.VBool()
			else:
				raise NotImplementedError
			if self.builder is not None:
				r.create_constant(v)
			return r
		elif isinstance(node, ast.Num):
			n = node.n
			if isinstance(n, int):
				if abs(n) < 2**31:
					r = ir_values.VInt()
				else:
					r = ir_values.VInt(64)
			else:
				raise NotImplementedError
			if self.builder is not None:
				r.create_constant(n)
			return r
		elif isinstance(node, ast.UnaryOp):
			return _ast_unops[type(node.op)](self.visit(node.operand), self.builder)
		elif isinstance(node, ast.BinOp):
			return _ast_binops[type(node.op)](self.visit(node.left), self.visit(node.right), self.builder)
		elif isinstance(node, ast.Compare):
			comparisons = []
			old_comparator = self.visit(node.left)
			for op, comparator_a in zip(node.ops, node.comparators):
				comparator = self.visit(comparator_a)
				comparison = _ast_cmps[type(op)](old_comparator, comparator)
				comparisons.append(comparison)
				old_comparator = comparator
			r = comparisons[0]
			for comparison in comparisons[1:]:
				r = ir_values.operators.and_(r, comparison)
			return r
		elif isinstance(node, ast.Call):
			return _ast_unfuns[node.func.id](self.visit(node.args[0]), self.builder)
		else:
			raise NotImplementedError
