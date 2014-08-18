from collections import namedtuple, defaultdict
from fractions import Fraction
import inspect, textwrap, ast

from artiq.compiler.tools import eval_ast, value_to_ast
from artiq.language import core as core_language
from artiq.language import units

_UserVariable = namedtuple("_UserVariable", "name")

def _is_in_attr_list(obj, attr, al):
	if not hasattr(obj, al):
		return False
	return attr in getattr(obj, al).split()

class _ReferenceManager:
	def __init__(self):
		# (id(obj), funcname, local) -> _UserVariable(name) / ast / constant_object
		# local is None for kernel attributes
		self.to_inlined = dict()
		# inlined_name -> use_count
		self.use_count = dict()
		self.rpc_map = defaultdict(lambda: len(self.rpc_map))
		self.kernel_attr_init = []

		# reserved names
		for kg in core_language.kernel_globals:
			self.use_count[kg] = 1
		self.use_count["range"] = 1
		self.use_count["int"] = 1
		self.use_count["round"] = 1
		self.use_count["int64"] = 1
		self.use_count["round64"] = 1
		self.use_count["Fraction"] = 1
		self.use_count["Quantity"] = 1
		self.use_count["s_unit"] = 1
		self.use_count["Hz_unit"] = 1

	def new_name(self, base_name):
		if base_name[-1].isdigit():
			base_name += "_"
		if base_name in self.use_count:
			r = base_name + str(self.use_count[base_name])
			self.use_count[base_name] += 1
			return r
		else:
			self.use_count[base_name] = 1
			return base_name

	def get(self, obj, funcname, ref):
		store = isinstance(ref.ctx, ast.Store)

		if isinstance(ref, ast.Name):
			key = (id(obj), funcname, ref.id)
			try:
				return self.to_inlined[key]
			except KeyError:
				if store:
					ival = _UserVariable(self.new_name(ref.id))
					self.to_inlined[key] = ival
					return ival

		if isinstance(ref, ast.Attribute) and isinstance(ref.value, ast.Name):
			try:
				value = self.to_inlined[(id(obj), funcname, ref.value.id)]
			except KeyError:
				pass
			else:
				if _is_in_attr_list(value, ref.attr, "kernel_attr_ro"):
					if store:
						raise TypeError("Attempted to assign to read-only kernel attribute")
					return getattr(value, ref.attr)
				if _is_in_attr_list(value, ref.attr, "kernel_attr"):
					key = (id(value), ref.attr, None)
					try:
						ival = self.to_inlined[key]
						assert(isinstance(ival, _UserVariable))
					except KeyError:
						iname = self.new_name(ref.attr)
						ival = _UserVariable(iname)
						self.to_inlined[key] = ival
						a = value_to_ast(getattr(value, ref.attr))
						if a is None:
							raise NotImplementedError("Cannot represent initial value of kernel attribute")
						self.kernel_attr_init.append(ast.Assign(
							[ast.Name(iname, ast.Store())], a))
					return ival

		if not store:
			evd = self.get_constants(obj, funcname)
			evd.update(inspect.getmodule(obj).__dict__)
			return eval_ast(ref, evd)
		else:
			raise KeyError

	def set(self, obj, funcname, name, value):
		self.to_inlined[(id(obj), funcname, name)] = value

	def get_constants(self, r_obj, r_funcname):
		return {local: v for (objid, funcname, local), v
			in self.to_inlined.items()
			if objid == id(r_obj)
			and funcname == r_funcname
			and not isinstance(v, (_UserVariable, ast.AST))}

_embeddable_calls = {
	core_language.delay, core_language.at, core_language.now,
	core_language.syscall,
	range, int, round, core_language.int64, core_language.round64,
	Fraction, units.Quantity
}

class _ReferenceReplacer(ast.NodeTransformer):
	def __init__(self, core, rm, obj, funcname):
		self.core = core
		self.rm = rm
		self.obj = obj
		self.funcname = funcname

	def visit_ref(self, node):
		store = isinstance(node.ctx, ast.Store)
		ival = self.rm.get(self.obj, self.funcname, node)
		if isinstance(ival, _UserVariable):
			newnode = ast.Name(ival.name, node.ctx)
		elif isinstance(ival, ast.AST):
			assert(not store)
			newnode = ival
		else:
			if store:
				raise NotImplementedError("Cannot turn object into user variable")
			else:
				newnode = value_to_ast(ival)
				if newnode is None:
					raise NotImplementedError("Cannot represent inlined value")
		return ast.copy_location(newnode, node)

	visit_Name = visit_ref
	visit_Attribute = visit_ref
	visit_Subscript = visit_ref

	def visit_Call(self, node):
		func = self.rm.get(self.obj, self.funcname, node.func)
		new_args = [self.visit(arg) for arg in node.args]

		if func in _embeddable_calls:
			new_func = ast.Name(func.__name__, ast.Load())
			return ast.copy_location(
				ast.Call(func=new_func, args=new_args,
				keywords=[], starargs=None, kwargs=None),
				node)
		elif hasattr(func, "k_function_info") and getattr(func.__self__, func.k_function_info.core_name) is self.core:
			args = [func.__self__] + new_args
			inlined, _ = inline(self.core, func.k_function_info.k_function, args, dict(), self.rm)
			return inlined.body
		else:
			args = [ast.Str("rpc"), value_to_ast(self.rm.rpc_map[func])]
			args += new_args
			return ast.copy_location(
				ast.Call(func=ast.Name("syscall", ast.Load()),
				args=args, keywords=[], starargs=None, kwargs=None),
				node)

	def visit_Expr(self, node):
		if isinstance(node.value, ast.Call):
			r = self.visit_Call(node.value)
			if isinstance(r, list):
				return r
			else:
				node.value = r
				return node
		else:
			self.generic_visit(node)
			return node

	def visit_FunctionDef(self, node):
		node.args = ast.arguments(args=[], vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[])
		node.decorator_list = []
		self.generic_visit(node)
		return node

class _ListReadOnlyParams(ast.NodeVisitor):
	def visit_FunctionDef(self, node):
		if hasattr(self, "read_only_params"):
			raise ValueError("More than one function definition")
		self.read_only_params = {arg.arg for arg in node.args.args}
		self.generic_visit(node)

	def visit_Name(self, node):
		if isinstance(node.ctx, ast.Store):
			try:
				self.read_only_params.remove(node.id)
			except KeyError:
				pass

def _list_read_only_params(funcdef):
	lrp = _ListReadOnlyParams()
	lrp.visit(funcdef)
	return lrp.read_only_params

def _initialize_function_params(funcdef, k_args, k_kwargs, rm):
	obj = k_args[0]
	funcname = funcdef.name
	param_init = []
	rop = _list_read_only_params(funcdef)
	for arg_ast, arg_value in zip(funcdef.args.args, k_args):
		arg_name = arg_ast.arg
		if arg_name in rop:
			rm.set(obj, funcname, arg_name, arg_value)
		else:
			target = rm.get(obj, funcname, ast.Name(arg_name, ast.Store()))
			value = value_to_ast(arg_value)
			param_init.append(ast.Assign(targets=[target], value=value))
	return param_init

def inline(core, k_function, k_args, k_kwargs, rm=None):
	init_kernel_attr = rm is None
	if rm is None:
		rm = _ReferenceManager()

	funcdef = ast.parse(textwrap.dedent(inspect.getsource(k_function))).body[0]

	param_init = _initialize_function_params(funcdef, k_args, k_kwargs, rm)

	obj = k_args[0]
	funcname = funcdef.name
	rr = _ReferenceReplacer(core, rm, obj, funcname)
	rr.visit(funcdef)

	funcdef.body[0:0] = param_init
	if init_kernel_attr:
		funcdef.body[0:0] = rm.kernel_attr_init

	r_rpc_map = dict((rpc_num, rpc_fun) for rpc_fun, rpc_num in rm.rpc_map.items())
	return funcdef, r_rpc_map
