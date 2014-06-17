from operator import itemgetter

from artiq.compiler.inline import inline
from artiq.compiler.unparse import Unparser

class Core:
	def run(self, k_function, k_args, k_kwargs):
		stmts, rpc_map = inline(self, k_function, k_args, k_kwargs)

		print("=========================")
		print(" Inlined")
		print("=========================")
		Unparser(stmts)

		print("")
		print("=========================")
		print(" RPC map")
		print("=========================")
		for rpc_func, rpc_num in sorted(rpc_map.items(), key=itemgetter(1)):
			print("{:3} -> {}".format(rpc_num, str(rpc_func)))
