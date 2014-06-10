import itertools

class Experiment:
	channels = ""
	parameters = ""

	def __init__(self, *args, **kwargs):
		channels = self.channels.split()
		parameters = self.parameters.split()
		argnames = channels + parameters
		undef_args = list(argnames)

		if len(argnames) < len(args):
			raise TypeError("__init__() takes {} positional arguments but {} were given".format(len(argnames), len(args)))
		for argname, value in itertools.chain(zip(argnames, args), kwargs.items()):
			if hasattr(self, argname):
				raise TypeError("__init__() got multiple values for argument '{}'".format(argname))
			if argname not in argnames:
				raise TypeError("__init__() got an unexpected keyword argument: '{}'".format(argname))
			setattr(self, argname, value)
			undef_args.remove(argname)
		if undef_args:
			raise TypeError("__init__() missing {} argument(s): ".format(len(undef_args),
				", ".join(["'"+s+"'" for s in undef_args])))

		self.kernel_attr_ro = set(parameters)

def kernel(arg):
	if isinstance(arg, str):
		def real_decorator(k_function):
			def run_on_core(exp, *k_args, **k_kwargs):
				getattr(exp, arg).run(k_function, exp, *k_args, **k_kwargs)
			return run_on_core	
		return real_decorator
	else:
		def run_on_core(exp, *k_args, **k_kwargs):
			exp.core.run(arg, exp, *k_args, **k_kwargs)
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

# global namespace for interpreted kernels

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
