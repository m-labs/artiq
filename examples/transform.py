import inspect, textwrap, ast

from artiq import units, unparse

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

def eval_ast(expr, symdict=dict()):
	if not isinstance(expr, ast.Expression):
		expr = ast.Expression(expr)
	code = compile(expr, "<ast>", "eval")
	return eval(code, symdict)

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

if __name__ == "__main__":
	import collapse_test
	kernel = collapse_test.collapse_test

	node = ast.parse(textwrap.dedent(inspect.getsource(kernel)))
	node = find_kernel_body(node)

	explicit_delays(node)
	unroll_loops(node, 50)

	unparse.Unparser(node)
