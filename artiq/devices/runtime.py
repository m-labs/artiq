from llvm import core as lc

_syscalls = [
	("print_int",	lc.Type.void(),		[lc.Type.int()]),
	("gpio_set",	lc.Type.void(),		[lc.Type.int(), lc.Type.int()])
]

class Environment:
	def __init__(self, module):
		for func_name, func_type_ret, func_type_args in _syscalls:
			function_type = lc.Type.function(func_type_ret, func_type_args)
			module.add_function(function_type, "__syscall_"+func_name)

		self.module = module

	def emit_syscall(self, builder, syscall_name, args):
		builder.call(self.module.get_function_named("__syscall_"+syscall_name), args)
