from artiq.compiler.inline import inline
from artiq.compiler.fold_constants import fold_constants
from artiq.compiler.unroll_loops import unroll_loops
from artiq.compiler.interleave import interleave
from artiq.compiler.ir import get_runtime_binary

class Core:
	def __init__(self, runtime_env, core_com):
		self.runtime_env = runtime_env
		self.core_com = core_com

	def run(self, k_function, k_args, k_kwargs):
		stmts, rpc_map = inline(self, k_function, k_args, k_kwargs)
		fold_constants(stmts)
		unroll_loops(stmts, 50)
		interleave(stmts)

		binary = get_runtime_binary(self.runtime_env, stmts)
		self.core_com.run(binary)
