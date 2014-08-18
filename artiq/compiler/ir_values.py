from types import SimpleNamespace

from llvm import core as lc

# None type

class VNone:
	def __repr__(self):
		return "<VNone>"

	def same_type(self, other):
		return isinstance(other, VNone)

	def merge(self, other):
		if not isinstance(other, VNone):
			raise TypeError

	def create_alloca(self, builder, name):
		pass

	def o_bool(self, builder):
		r = VBool()
		if builder is not None:
			r.create_constant(False)
		return r

# Integer type

class VInt:
	def __init__(self, nbits=32, llvm_value=None):
		self.nbits = nbits
		self.llvm_value = llvm_value

	def __repr__(self):
		return "<VInt:{}>".format(self.nbits)

	def same_type(self, other):
		return isinstance(other, VInt) and other.nbits == self.nbits

	def merge(self, other):
		if isinstance(other, VInt) and not isinstance(other, VBool):
			if other.nbits > self.nbits:
				self.nbits = other.nbits
		else:
			raise TypeError

	def create_constant(self, n):
		self.llvm_value = lc.Constant.int(lc.Type.int(self.nbits), n)

	def create_alloca(self, builder, name):
		self.llvm_value = builder.alloca(lc.Type.int(self.nbits), name=name)

	def o_bool(self, builder):
		if builder is None:
			return VBool()
		else:
			zero = lc.Constant.int(lc.Type.int(self.nbits), 0)
			return VBool(llvm_value=builder.icmp(lc.ICMP_NE, self.llvm_value, zero))

	def o_int(self, builder):
		if builder is None:
			return VInt()
		else:
			if self.nbits == 32:
				return self
			else:
				raise NotImplementedError
	o_round = o_int

	def o_int64(self, builder):
		if builder is None:
			return VInt(64)
		else:
			if self.nbits == 64:
				return self
			else:
				raise NotImplementedError
	o_round64 = o_int64

def _make_vint_binop_method(builder_name):
	def binop_method(self, other, builder):
			if isinstance(other, VInt):
				nbits = max(self.nbits, other.nbits)
				if builder is None:
					return VInt(nbits)
				else:
					bf = getattr(builder, builder_name)
					return VInt(nbits, llvm_value=bf(self.llvm_value, other.llvm_value))
			else:
				return NotImplemented
	return binop_method

for _method_name, _builder_name in (
  ("o_add", "add"),
  ("o_sub", "sub"),
  ("o_mul", "mul"),
  ("o_floordiv", "sdiv"),
  ("o_mod", "srem"),
  ("o_and", "and_"),
  ("o_xor", "xor"),
  ("o_or", "or_")):
	setattr(VInt, _method_name, _make_vint_binop_method(_builder_name))	

def _make_vint_cmp_method(icmp_val):
	def cmp_method(self, other, builder):
		if isinstance(other, VInt):
			if builder is None:
				return VBool()
			else:
				return VBool(llvm_value=builder.icmp(icmp_val, self.llvm_value, other.llvm_value))
		else:
			return NotImplemented
	return cmp_method

for _method_name, _icmp_val in (
  ("o_eq", lc.ICMP_EQ),
  ("o_ne", lc.ICMP_NE),
  ("o_lt", lc.ICMP_SLT),
  ("o_le", lc.ICMP_SLE),
  ("o_gt", lc.ICMP_SGT),
  ("o_ge", lc.ICMP_SGE)):
	setattr(VInt, _method_name, _make_vint_cmp_method(_icmp_val))

# Boolean type

class VBool(VInt):
	def __init__(self, llvm_value=None):
		VInt.__init__(self, 1, llvm_value)

	def __repr__(self):
		return "<VBool>"

	def merge(self, other):
		if not isinstance(other, VBool):
			raise TypeError

	def create_constant(self, b):
		VInt.create_constant(self, int(b))

	def o_bool(self, builder):
		if builder is None:
			return VBool()
		else:
			return self

# Operators

def _make_unary_operator(op_name):
	def op(x, builder):
		try:
			opf = getattr(x, "o_"+op_name)
		except AttributeError:
			raise TypeError("Unsupported operand type for {}: {}".format(op_name, type(x).__name__))
		return opf(builder)
	return op

def _make_binary_operator(op_name):
	def op(l, r, builder):
		try:
			opf = getattr(l, "o_"+op_name)
		except AttributeError:
			result = NotImplemented
		else:
			result = opf(r, builder)
		if result is NotImplemented:
			try:
				ropf = getattr(l, "or_"+op_name)
			except AttributeError:
				result = NotImplemented
			else:
				result = ropf(r, builder)
			if result is NotImplemented:
				raise TypeError("Unsupported operand types for {}: {} and {}".format(
					op_name, type(l).__name__, type(r).__name__))
		return result
	return op

def _make_operators():
	d = dict()
	for op_name in ("bool", "int", "int64", "round", "round64", "inv", "pos", "neg"):
		d[op_name] = _make_unary_operator(op_name)
	d["not_"] = _make_binary_operator("not")
	for op_name in ("add", "sub", "mul",
	  "truediv", "floordiv", "mod",
	  "pow", "lshift", "rshift", "xor",
	  "eq", "ne", "lt", "le", "gt", "ge"):
		d[op_name] = _make_binary_operator(op_name)
	d["and_"] = _make_binary_operator("and")
	d["or_"] = _make_binary_operator("or")
	return SimpleNamespace(**d)

operators = _make_operators()
