import ast

def eval_ast(expr, symdict=dict()):
	if not isinstance(expr, ast.Expression):
		expr = ast.Expression(expr)
	code = compile(expr, "<ast>", "eval")
	return eval(code, symdict)#
