import inspect, textwrap, ast, types

from artiq.language import units
from artiq.compiler import unparse
from artiq.compiler.tools import eval_ast

def find_kernel_body(node):
	while True:
		if isinstance(node, ast.Module):
			if len(node.body) != 1:
				raise TypeError
			node = node.body[0]
		elif isinstance(node, ast.FunctionDef):
			return node.body
		else:
			raise TypeError

def _try_eval_with_units(node):
	try:
		r = eval_ast(node, units.__dict__)
	except:
		return node
	if isinstance(r, units.Quantity):
		return ast.copy_location(ast.Num(n=r.amount), node)
	else:
		return node

def explicit_delays(stmts):
	insertions = []
	for i, stmt in enumerate(stmts):
		if isinstance(stmt, (ast.For, ast.While, ast.If)):
			explicit_delays(stmt.body)
			explicit_delays(stmt.orelse)
		elif isinstance(stmt, ast.With):
			explicit_delays(stmt.body)
		elif isinstance(stmt, ast.Expr):
			if not isinstance(stmt.value, ast.Call) or not isinstance(stmt.value.func, ast.Name):
				continue
			call = stmt.value
			name = call.func.id
			if name == "delay":
				call.args[0] = _try_eval_with_units(call.args[0])
			elif name == "pulse":
				call.func.id = "pulse_start"
				insertions.append((i+1, ast.copy_location(
					ast.Expr(ast.Call(func=ast.Name(id="delay", ctx=ast.Load()),
						args=[_try_eval_with_units(call.args[2])],
						keywords=[], starargs=[], kwargs=[])),
					stmt)))
	for i, (location, stmt) in enumerate(insertions):
		stmts.insert(location+i, stmt)

def _count_stmts(node):
	if isinstance(node, (ast.For, ast.While, ast.If)):
		print(ast.dump(node))
		return 1 + _count_stmts(node.body) + _count_stmts(node.orelse)
	elif isinstance(node, ast.With):
		return 1 + _count_stmts(node.body)
	elif isinstance(node, list):
		return sum(map(_count_stmts, node))
	else:
		return 1

def unroll_loops(stmts, limit):
	replacements = []
	for stmt_i, stmt in enumerate(stmts):
		if isinstance(stmt, ast.For):
			try:
				it = eval_ast(stmt.iter)
			except:
				pass
			else:
				unroll_loops(stmt.body, limit)
				unroll_loops(stmt.orelse, limit)
				l_it = len(it)
				if l_it:
					n = l_it*_count_stmts(stmt.body)
					if n < limit:
						replacement = []
						for i in it:
							if not isinstance(i, int):
								replacement = None
								break
							replacement.append(ast.copy_location(
								ast.Assign(targets=[stmt.target], value=ast.Num(n=i)), stmt))
							replacement += stmt.body
						if replacement is not None:
							replacements.append((stmt_i, replacement))
				else:
					replacements.append((stmt_i, stmt.orelse))
		if isinstance(stmt, (ast.While, ast.If)):
			unroll_loops(stmt.body, limit)
			unroll_loops(stmt.orelse, limit)
		elif isinstance(stmt, ast.With):
			unroll_loops(stmt.body, limit)
	offset = 0
	for location, new_stmts in replacements:
		stmts[offset+location:offset+location+1] = new_stmts
		offset += len(new_stmts) - 1

# -1 statement duration could not be pre-determined
#  0 statement has no effect on timeline
# >0 statement is a static delay that advances the timeline by the given amount
def _get_duration(stmt):
	if isinstance(stmt, (ast.Expr, ast.Assign)):
		return _get_duration(stmt.value)
	elif isinstance(stmt, ast.Call) and isinstance(stmt.func, ast.Name):
		name = stmt.func.id
		if name == "delay":
			if isinstance(stmt.args[0], ast.Num):
				return stmt.args[0].n
			else:
				return -1
		elif name == "wait_edge":
			return -1
		else:
			return 0
	else:
		return -1

def _merge_timelines(timelines):
	r = []

	current_stmts = []
	for stmts in timelines:
		it = iter(stmts)
		try:
			stmt = next(it)
		except StopIteration:
			pass
		else:
			current_stmts.append(types.SimpleNamespace(delay=_get_duration(stmt), stmt=stmt, it=it))

	while current_stmts:
		dt = min(stmt.delay for stmt in current_stmts)
		if dt < 0:
			# contains statement(s) with indeterminate duration
			return None
		if dt > 0:
			# advance timeline by dt
			for stmt in current_stmts:
				stmt.delay -= dt
				if stmt.delay == 0:
					ref_stmt = stmt.stmt
			delay_stmt = ast.copy_location(
				ast.Expr(ast.Call(func=ast.Name(id="delay", ctx=ast.Load()),
					args=[ast.Num(n=dt)],
					keywords=[], starargs=[], kwargs=[])),
				ref_stmt)
			r.append(delay_stmt)
		else:
			for stmt in current_stmts:
				if stmt.delay == 0:
					r.append(stmt.stmt)
		# discard executed statements
		exhausted_list = []
		for stmt_i, stmt in enumerate(current_stmts):
			if stmt.delay == 0:
				try:
					stmt.stmt = next(stmt.it)
				except StopIteration:
					exhausted_list.append(stmt_i)
				else:
					stmt.delay = _get_duration(stmt.stmt)
		for offset, i in enumerate(exhausted_list):
			current_stmts.pop(i-offset)

	return r

def collapse(stmts):
	replacements = []
	for stmt_i, stmt in enumerate(stmts):
		if isinstance(stmt, (ast.For, ast.While, ast.If)):
			collapse(stmt.body)
			collapse(stmt.orelse)
		elif isinstance(stmt, ast.With):
			btype = stmt.items[0].context_expr.id
			if btype == "sequential":
				collapse(stmt.body)
				replacements.append((stmt_i, stmt.body))
			elif btype == "parallel":
				timelines = [[s] for s in stmt.body]
				for timeline in timelines:
					collapse(timeline)
				merged = _merge_timelines(timelines)
				if merged is not None:
					replacements.append((stmt_i, merged))
			else:
				raise ValueError("Unknown block type: " + btype)
	offset = 0
	for location, new_stmts in replacements:
		stmts[offset+location:offset+location+1] = new_stmts
		offset += len(new_stmts) - 1

def transform(k_function, k_args, k_kwargs):
	node = ast.parse(textwrap.dedent(inspect.getsource(k_function)))
	node = find_kernel_body(node)

	explicit_delays(node)
	unroll_loops(node, 50)
	collapse(node)

	unparse.Unparser(node)
