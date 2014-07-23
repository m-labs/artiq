import ast

from llvm import core as lc
from llvm import passes as lp

class _Namespace:
	def __init__(self, function):
		self.function = function
		self.bindings = dict()

	def store(self, builder, val, name):
		try:
			allocated = self.bindings[name]
		except KeyError:
			entry = self.function.get_entry_basic_block()
			builder_e = lc.Builder.new(entry)
			builder_e.position_at_beginning(entry)
			allocated = builder_e.alloca(lc.Type.int(), name=name)
			self.bindings[name] = allocated
		builder.store(val, allocated)

	def load(self, builder, name):
		return builder.load(self.bindings[name])

_binop_to_builder = {
	ast.Add: "add",
	ast.Sub: "sub",
	ast.Mult: "mul",
	ast.FloorDiv: "sdiv",
	ast.Mod: "srem",
	ast.LShift: "shl",
	ast.RShift: "ashr"
}

def _emit_expr(env, builder, ns, node):
	if isinstance(node, ast.Name):
		return ns.load(builder, node.id)
	elif isinstance(node, ast.Num):
		return lc.Constant.int(lc.Type.int(), node.n)
	elif isinstance(node, ast.BinOp):
		left = _emit_expr(env, builder, ns, node.left)
		right = _emit_expr(env, builder, ns, node.right)
		bf = getattr(builder, _binop_to_builder[type(node.op)])
		return bf(left, right)
	elif isinstance(node, ast.Compare):
		comparisons = []
		old_comparator = _emit_expr(env, builder, ns, node.left)
		for op, comparator_a in zip(node.ops, node.comparators):
			comparator = _emit_expr(env, builder, ns, comparator_a)
			mapping = {
				ast.Eq: lc.ICMP_EQ,
				ast.NotEq: lc.ICMP_NE,
				ast.Lt: lc.ICMP_SLT,
				ast.LtE: lc.ICMP_SLE,
				ast.Gt: lc.ICMP_SGT,
				ast.GtE: lc.ICMP_SGE
			}
			comparison = builder.icmp(mapping[type(op)], old_comparator, comparator)
			comparisons.append(comparison)
			old_comparator = comparator
		r = comparisons[0]
		for comparison in comparisons[1:]:
			r = builder.band(r, comparison)
		return r
	elif isinstance(node, ast.Call):
		if node.func.id == "syscall":
			return env.emit_syscall(builder, node.args[0].s,
				[_emit_expr(env, builder, ns, expr) for expr in node.args[1:]])
		elif node.func.id == "Quantity":
			return _emit_expr(env, builder, ns, node.args[0])
		else:
			raise NotImplementedError
	else:
		raise NotImplementedError

def _emit_statements(env, builder, ns, stmts):
	for stmt in stmts:
		if isinstance(stmt, ast.Return):
			val = _emit_expr(env, builder, ns, stmt.value)
			builder.ret(val)
		elif isinstance(stmt, ast.Assign):
			val = _emit_expr(env, builder, ns, stmt.value)
			for target in stmt.targets:
				if isinstance(target, ast.Name):
					ns.store(builder, val, target.id)
				else:
					raise NotImplementedError
		elif isinstance(stmt, ast.AugAssign):
			left = _emit_expr(env, builder, ns, stmt.target)
			right = _emit_expr(env, builder, ns, stmt.value)
			bf = getattr(builder, _binop_to_builder[type(stmt.op)])
			result = bf(left, right)
			ns.store(builder, result, stmt.target.id)
		elif isinstance(stmt, ast.If):
			function = builder.basic_block.function
			then_block = function.append_basic_block("i_then")
			else_block = function.append_basic_block("i_else")
			merge_block = function.append_basic_block("i_merge")

			condition = _emit_expr(env, builder, ns, stmt.test)
			builder.cbranch(condition, then_block, else_block)

			builder.position_at_end(then_block)
			_emit_statements(env, builder, ns, stmt.body)
			builder.branch(merge_block)

			builder.position_at_end(else_block)
			_emit_statements(env, builder, ns, stmt.orelse)
			builder.branch(merge_block)

			builder.position_at_end(merge_block)
		elif isinstance(stmt, ast.While):
			function = builder.basic_block.function
			body_block = function.append_basic_block("w_body")
			else_block = function.append_basic_block("w_else")
			merge_block = function.append_basic_block("w_merge")

			condition = _emit_expr(env, builder, ns, stmt.test)
			builder.cbranch(condition, body_block, else_block)

			builder.position_at_end(body_block)
			_emit_statements(env, builder, ns, stmt.body)
			condition = _emit_expr(env, builder, ns, stmt.test)
			builder.cbranch(condition, body_block, merge_block)

			builder.position_at_end(else_block)
			_emit_statements(env, builder, ns, stmt.orelse)
			builder.branch(merge_block)

			builder.position_at_end(merge_block)
		elif isinstance(stmt, ast.Expr):
			_emit_expr(env, builder, ns, stmt.value)
		else:
			raise NotImplementedError

def get_runtime_binary(env, stmts):
	module = lc.Module.new("main")
	env.set_module(module)

	function_type = lc.Type.function(lc.Type.void(), [])
	function = module.add_function(function_type, "run")
	bb = function.append_basic_block("entry")
	builder = lc.Builder.new(bb)
	ns = _Namespace(function)
	_emit_statements(env, builder, ns, stmts)
	builder.ret_void()

	pass_manager = lp.PassManager.new()
	pass_manager.add(lp.PASS_MEM2REG)
	pass_manager.add(lp.PASS_INSTCOMBINE)
	pass_manager.add(lp.PASS_REASSOCIATE)
	pass_manager.add(lp.PASS_GVN)
	pass_manager.add(lp.PASS_SIMPLIFYCFG)
	pass_manager.run(module)

	return env.emit_object()
