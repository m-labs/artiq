from artiq.compiler.inline import inline

class Core:
	def run(self, k_function, k_args, k_kwargs):
		inline(k_function, k_args, k_kwargs)
