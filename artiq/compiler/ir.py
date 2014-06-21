import ast

from llvm import core as lc

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

def _emit_expr(builder, ns, node):
	if isinstance(node, ast.Name):
		return ns.load(builder, node.id)
	elif isinstance(node, ast.Num):
		return lc.Constant.int(lc.Type.int(), node.n)
	elif isinstance(node, ast.BinOp):
		left = _emit_expr(builder, ns, node.left)
		right = _emit_expr(builder, ns, node.right)
		mapping = {
			ast.Add: builder.add,
			ast.Sub: builder.sub,
			ast.Mult: builder.mul,
			ast.FloorDiv: builder.sdiv,
			ast.Mod: builder.srem
		}
		bf = mapping[type(node.op)]
		return bf(left, right)
	elif isinstance(node, ast.Compare):
		comparisons = []
		old_comparator = _emit_expr(builder, ns, node.left)
		for op, comparator_a in zip(node.ops, node.comparators):
			comparator = _emit_expr(builder, ns, comparator_a)
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
	else:
		raise NotImplementedError

def _emit_statements(builder, ns, stmts):
	for stmt in stmts:
		if isinstance(stmt, ast.Return):
			val = _emit_expr(builder, ns, stmt.value)
			builder.ret(val)
		elif isinstance(stmt, ast.Assign):
			val = _emit_expr(builder, ns, stmt.value)
			for target in stmt.targets:
				if isinstance(target, ast.Name):
					ns.store(builder, val, target.id)
				else:
					raise NotImplementedError
		elif isinstance(stmt, ast.If):
			function = builder.basic_block.function
			then_block = function.append_basic_block("i_then")
			else_block = function.append_basic_block("i_else")
			merge_block = function.append_basic_block("i_merge")

			condition = _emit_expr(builder, ns, stmt.test)
			builder.cbranch(condition, then_block, else_block)

			builder.position_at_end(then_block)
			_emit_statements(builder, ns, stmt.body)
			builder.branch(merge_block)

			builder.position_at_end(else_block)
			_emit_statements(builder, ns, stmt.orelse)
			builder.branch(merge_block)

			builder.position_at_end(merge_block)
		elif isinstance(stmt, ast.While):
			function = builder.basic_block.function
			body_block = function.append_basic_block("w_body")
			else_block = function.append_basic_block("w_else")
			merge_block = function.append_basic_block("w_merge")

			condition = _emit_expr(builder, ns, stmt.test)
			builder.cbranch(condition, body_block, else_block)

			builder.position_at_end(body_block)
			_emit_statements(builder, ns, stmt.body)
			condition = _emit_expr(builder, ns, stmt.test)
			builder.cbranch(condition, body_block, merge_block)

			builder.position_at_end(else_block)
			_emit_statements(builder, ns, stmt.orelse)
			builder.branch(merge_block)

			builder.position_at_end(merge_block)
		else:
			raise NotImplementedError

def _emit_function_def(module, node):
	function_type = lc.Type.function(lc.Type.int(), [lc.Type.int()]*len(node.args.args))
	function = module.add_function(function_type, node.name)
	bb = function.append_basic_block("entry")
	builder = lc.Builder.new(bb)

	ns = _Namespace(function)
	for ast_arg, llvm_arg in zip(node.args.args, function.args):
		llvm_arg.name = ast_arg.arg
		ns.store(builder, llvm_arg, ast_arg.arg)

	_emit_statements(builder, ns, node.body)

if __name__ == "__main__":
	from llvm import target as lt
	from llvm import passes as lp
	import subprocess

	testcode = """
def is_prime(x):
	d = 2
	while d*d <= x:
		if x % d == 0:
			return 0
		d = d + 1
	return 1
"""

	node = ast.parse(testcode)
	fdef = node.body[0]
	my_module = lc.Module.new("my_module")
	_emit_function_def(my_module, fdef)

	pass_manager = lp.PassManager.new()
	pass_manager.add(lp.PASS_MEM2REG)
	pass_manager.add(lp.PASS_INSTCOMBINE)
	pass_manager.add(lp.PASS_REASSOCIATE)
	pass_manager.add(lp.PASS_GVN)
	pass_manager.add(lp.PASS_SIMPLIFYCFG)
	pass_manager.run(my_module)

	lt.initialize_all()
	tm = lt.TargetMachine.new(triple="or1k", cpu="generic")
	with open("test.out", "wb") as fout:
		objfile = tm.emit_object(my_module)
		fout.write(objfile)

	print("=========================")
	print(" LLVM IR")
	print("=========================")
	print(my_module)

	print("")
	print("=========================")
	print(" OR1K ASM")
	print("=========================")
	subprocess.call("or1k-elf-objdump -d test.out".split())
