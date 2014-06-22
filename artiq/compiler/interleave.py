import ast, types

from artiq.language import units
from artiq.compiler.tools import eval_ast

# -1 statement duration could not be pre-determined
#  0 statement has no effect on timeline
# >0 statement is a static delay that advances the timeline
#     by the given amount (in base_s_unit)
def _get_duration(stmt):
	if isinstance(stmt, (ast.Expr, ast.Assign)):
		return _get_duration(stmt.value)
	elif isinstance(stmt, ast.If):
		if all(_get_duration(s) == 0 for s in stmt.body) and all(_get_duration(s) == 0 for s in stmt.orelse):
			return 0
		else:
			return -1
	elif isinstance(stmt, ast.Call) and isinstance(stmt.func, ast.Name):
		name = stmt.func.id
		if name == "delay":
			da = stmt.args[0]
			if isinstance(da, ast.Call) \
			  and isinstance(da.func, ast.Name) \
			  and da.func.id == "Quantity" \
			  and isinstance(da.args[0], ast.Num):
				if not isinstance(da.args[1], ast.Name) or da.args[1].id != "base_s_unit":
					raise units.DimensionError("Delay not expressed in seconds")
				return da.args[0].n
			else:
				return -1
		else:
			return 0
	else:
		return 0

def _interleave_timelines(timelines):
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
		print("\n".join("{} -> {}".format(ast.dump(stmt.stmt), stmt.delay) for stmt in current_stmts))
		print("")
		if dt < 0:
			# contains statement(s) with indeterminate duration
			return None
		if dt > 0:
			# advance timeline by dt
			for stmt in current_stmts:
				stmt.delay -= dt
				if stmt.delay == 0:
					ref_stmt = stmt.stmt
			da_expr = ast.copy_location(
					ast.Call(func=ast.Name("Quantity", ast.Load()),
					args=[ast.Num(dt), ast.Name("base_s_unit", ast.Load())],
					keywords=[], starargs=[], kwargs=[]),
				ref_stmt)
			delay_stmt = ast.copy_location(
				ast.Expr(ast.Call(func=ast.Name("delay", ast.Load()),
					args=[da_expr],
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

def interleave(stmts):
	replacements = []
	for stmt_i, stmt in enumerate(stmts):
		if isinstance(stmt, (ast.For, ast.While, ast.If)):
			interleave(stmt.body)
			interleave(stmt.orelse)
		elif isinstance(stmt, ast.With):
			btype = stmt.items[0].context_expr.id
			if btype == "sequential":
				interleave(stmt.body)
				replacements.append((stmt_i, stmt.body))
			elif btype == "parallel":
				timelines = [[s] for s in stmt.body]
				for timeline in timelines:
					interleave(timeline)
				merged = _interleave_timelines(timelines)
				if merged is not None:
					replacements.append((stmt_i, merged))
			else:
				raise ValueError("Unknown block type: " + btype)
	offset = 0
	for location, new_stmts in replacements:
		stmts[offset+location:offset+location+1] = new_stmts
		offset += len(new_stmts) - 1
