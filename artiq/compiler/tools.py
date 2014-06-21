import ast

from artiq.language import experiment, units

def eval_ast(expr, symdict=dict()):
	if not isinstance(expr, ast.Expression):
		expr = ast.Expression(expr)
	code = compile(expr, "<ast>", "eval")
	return eval(code, symdict)

def value_to_ast(value):
	if isinstance(value, int):
		return ast.Num(value)
	elif isinstance(value, str):
		return ast.Str(value)
	else:
		for kg in experiment.kernel_globals:
			if value is getattr(experiment, kg):
				return ast.Name(kg, ast.Load())
		if isinstance(value, units.Quantity):
			return ast.Call(
					func=ast.Name("Quantity", ast.Load()),
					args=[ast.Num(value.amount), ast.Name("base_"+value.unit.name+"_unit", ast.Load())],
					keywords=[], starargs=None, kwargs=None)
		return None

def make_stmt_transformer(transformer_class):
	def stmt_transformer(stmts, *args, **kwargs):
		transformer = transformer_class(*args, **kwargs)
		new_stmts = [transformer.visit(stmt) for stmt in stmts]
		stmts[:] = new_stmts
	return stmt_transformer
