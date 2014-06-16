from artiq.compiler.inline import inline
from artiq.compiler.unparse import Unparser

class Core:
	def run(self, k_function, k_args, k_kwargs):
		stmts = inline(k_function, k_args, k_kwargs)
		Unparser(stmts)
