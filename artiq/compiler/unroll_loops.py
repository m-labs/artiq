import ast

from artiq.compiler.tools import eval_ast, value_to_ast

def _count_stmts(node):
	if isinstance(node, (ast.For, ast.While, ast.If)):
		return 1 + _count_stmts(node.body) + _count_stmts(node.orelse)
	elif isinstance(node, ast.With):
		return 1 + _count_stmts(node.body)
	elif isinstance(node, list):
		return sum(map(_count_stmts, node))
	else:
		return 1

class _LoopUnroller(ast.NodeTransformer):
	def __init__(self, limit):
		self.limit = limit

	def visit_For(self, node):
		self.generic_visit(node)
		try:
			it = eval_ast(node.iter)
		except:
			return node
		l_it = len(it)
		if l_it:
			n = l_it*_count_stmts(node.body)
			if n < self.limit:
				replacement = []
				for i in it:
					if not isinstance(i, int):
						replacement = None
						break
					replacement.append(ast.copy_location(
						ast.Assign(targets=[node.target], value=value_to_ast(i)), node))
					replacement += node.body
				if replacement is not None:
					return replacement
				else:
					return node
			else:
				return node
		else:
			return node.orelse

def unroll_loops(node, limit):
	_LoopUnroller(limit).visit(node)
