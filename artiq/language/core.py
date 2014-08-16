from collections import namedtuple
from fractions import Fraction

from artiq.language import units

class int64(int):
	pass

def _make_int64_op_method(int_method):
	def method(self, *args):
		r = int_method(self, *args)
		if isinstance(r, int):
			r = int64(r)
		return r
	return method

for _op_name in (
  "neg", "pos", "abs", "invert", "round",
  "add", "radd", "sub", "rsub", "mul", "rmul", "pow", "rpow",
  "lshift", "rlshift", "rshift", "rrshift",
  "and", "rand", "xor", "rxor", "or", "ror",
  "floordiv", "rfloordiv", "mod", "rmod"):
	method_name = "__" + _op_name + "__"
	orig_method = getattr(int, method_name)
	setattr(int64, method_name, _make_int64_op_method(orig_method))

for _op_name in (
  "add", "sub", "mul", "floordiv", "mod",
  "pow", "lshift", "rshift", "lshift",
  "and", "xor", "or"):
	op_method = getattr(int, "__" + _op_name + "__")
	setattr(int64, "__i" + _op_name + "__", _make_int64_op_method(op_method))

def round64(x):
	return int64(round(x))

def _make_kernel_ro(value):
	return isinstance(value, (bool, int, int64, float, Fraction, units.Quantity))

class AutoContext:
	parameters = ""
	implicit_core = True

	def __init__(self, mvs=None, **kwargs):
		kernel_attr_ro = []

		self.mvs = mvs
		for k, v in kwargs.items():
			setattr(self, k, v)
			if _make_kernel_ro(v):
				kernel_attr_ro.append(k)

		parameters = self.parameters.split()
		if self.implicit_core:
			parameters.append("core")
		for parameter in parameters:
			try:
				value = getattr(self, parameter)
			except AttributeError:
				value = self.mvs.get_missing_value(parameter)
				setattr(self, parameter, value)
			if _make_kernel_ro(value):
				kernel_attr_ro.append(parameter)
				
		self.kernel_attr_ro = " ".join(kernel_attr_ro)

		self.build()

	def get_missing_value(self, parameter):
		try:
			return getattr(self, parameter)
		except AttributeError:
			return self.mvs.get_missing_value(parameter)

	def build(self):
		""" Overload this function to add sub-experiments"""
		pass

KernelFunctionInfo = namedtuple("KernelFunctionInfo", "core_name k_function")

def kernel(arg):
	if isinstance(arg, str):
		def real_decorator(k_function):
			def run_on_core(exp, *k_args, **k_kwargs):
				getattr(exp, arg).run(k_function, ((exp,) + k_args), k_kwargs)
			run_on_core.k_function_info = KernelFunctionInfo(core_name=arg, k_function=k_function)
			return run_on_core
		return real_decorator
	else:
		def run_on_core(exp, *k_args, **k_kwargs):
			exp.core.run(arg, ((exp,) + k_args), k_kwargs)
		run_on_core.k_function_info = KernelFunctionInfo(core_name="core", k_function=arg)
		return run_on_core

class _DummyTimeManager:
	def _not_implemented(self, *args, **kwargs):
		raise NotImplementedError("Attempted to interpret kernel without a time manager")

	enter_sequential = _not_implemented
	enter_parallel = _not_implemented
	exit = _not_implemented
	take_time = _not_implemented
	get_time = _not_implemented
	set_time = _not_implemented

_time_manager = _DummyTimeManager()

def set_time_manager(time_manager):
	global _time_manager
	_time_manager = time_manager

class _DummySyscallManager:
	def do(self, *args):
		raise NotImplementedError("Attempted to interpret kernel without a syscall manager")

_syscall_manager = _DummySyscallManager()

def set_syscall_manager(syscall_manager):
	global _syscall_manager
	_syscall_manager = syscall_manager

# global namespace for kernels

kernel_globals = "sequential", "parallel", "delay", "now", "at", "syscall"

class _Sequential:
	def __enter__(self):
		_time_manager.enter_sequential()

	def __exit__(self, type, value, traceback):
		_time_manager.exit()
sequential = _Sequential()

class _Parallel:
	def __enter__(self):
		_time_manager.enter_parallel()

	def __exit__(self, type, value, traceback):
		_time_manager.exit()
parallel = _Parallel()

def delay(duration):
	_time_manager.take_time(duration)

def now():
	return _time_manager.get_time()

def at(time):
	_time_manager.set_time(time)

def syscall(*args):
	return _syscall_manager.do(*args)
