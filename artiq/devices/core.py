from artiq.compiler.transform import transform

class Core:
	def run(self, k_function, *k_args, **k_kwargs):
		transform(k_function, k_args, k_kwargs)
