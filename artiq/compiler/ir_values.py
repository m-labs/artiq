from types import SimpleNamespace

from llvm import core as lc

class _Value:
	def __init__(self):
		self._llvm_value = None

	def get_ssa_value(self, builder):
		if isinstance(self._llvm_value, lc.AllocaInstruction):
			return builder.load(self._llvm_value)
		else:
			return self._llvm_value

	def set_ssa_value(self, builder, value):
		if self._llvm_value is None:
			self._llvm_value = value
		elif isinstance(self._llvm_value, lc.AllocaInstruction):
			builder.store(value, self._llvm_value)
		else:
			raise RuntimeError("Attempted to set LLVM SSA value multiple times")

	def alloca(self, builder, name):
		if self._llvm_value is not None:
			raise RuntimeError("Attempted to alloca existing LLVM value")
		self._llvm_value = builder.alloca(self.get_llvm_type(), name=name)

	def o_int(self, builder):
		return self.o_intx(32, builder)

	def o_int64(self, builder):
		return self.o_intx(64, builder)

	def o_round(self, builder):
		return self.o_roundx(32, builder)

	def o_round64(self, builder):
		return self.o_roundx(64, builder)

# None type

class VNone(_Value):
	def __repr__(self):
		return "<VNone>"

	def get_llvm_type(self):
		return lc.Type.void()

	def same_type(self, other):
		return isinstance(other, VNone)

	def merge(self, other):
		if not isinstance(other, VNone):
			raise TypeError

	def alloca(self, builder, name):
		pass

	def o_bool(self, builder):
		r = VBool()
		if builder is not None:
			r.set_const_value(builder, False)
		return r

# Integer type

class VInt(_Value):
	def __init__(self, nbits=32):
		_Value.__init__(self)
		self.nbits = nbits

	def get_llvm_type(self):
		return lc.Type.int(self.nbits)

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

	def set_value(self, builder, n):
		self.set_ssa_value(builder, n.o_intx(self.nbits, builder).get_ssa_value(builder))

	def set_const_value(self, builder, n):
		self.set_ssa_value(builder, lc.Constant.int(self.get_llvm_type(), n))

	def o_bool(self, builder):
		r = VBool()
		if builder is not None:
			r.set_ssa_value(builder, builder.icmp(lc.ICMP_NE,
				self.get_ssa_value(builder), lc.Constant.int(self.get_llvm_type(), 0)))
		return r

	def o_intx(self, target_bits, builder):
		r = VInt(target_bits)
		if builder is not None:
			if self.nbits == target_bits:
				r.set_ssa_value(builder, self.get_ssa_value(builder))
			if self.nbits > target_bits:
				r.set_ssa_value(builder, builder.trunc(self.get_ssa_value(builder), r.get_llvm_type()))
			if self.nbits < target_bits:
				r.set_ssa_value(builder, builder.sext(self.get_ssa_value(builder), r.get_llvm_type()))
		return r
	o_roundx = o_intx

def _make_vint_binop_method(builder_name):
	def binop_method(self, other, builder):
			if isinstance(other, VInt):
				target_bits = max(self.nbits, other.nbits)
				r = VInt(target_bits)
				if builder is not None:
					left = self.o_intx(target_bits, builder)
					right = other.o_intx(target_bits, builder)
					bf = getattr(builder, builder_name)
					r.set_ssa_value(builder,
						bf(left.get_ssa_value(builder), right.get_ssa_value(builder)))
				return r
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
			r = VBool()
			if builder is not None:
				target_bits = max(self.nbits, other.nbits)
				left = self.o_intx(target_bits, builder)
				right = other.o_intx(target_bits, builder)
				r.set_ssa_value(builder, 
					builder.icmp(icmp_val, left.get_ssa_value(builder), right.get_ssa_value(builder)))
			return r
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
	def __init__(self):
		VInt.__init__(self, 1)

	def __repr__(self):
		return "<VBool>"

	def same_type(self, other):
		return isinstance(other, VBool)

	def merge(self, other):
		if not isinstance(other, VBool):
			raise TypeError

	def set_const_value(self, builder, b):
		VInt.set_const_value(self, builder, int(b))

	def o_bool(self, builder):
		r = VBool()
		if builder is not None:
			r.set_ssa_value(builder, self.get_ssa_value(builder))
		return r

# Fraction type

class VFraction(_Value):
	def get_llvm_type(self):
		return lc.Type.vector(lc.Type.int(64), 2)

	def __repr__(self):
		return "<VFraction>"

	def same_type(self, other):
		return isinstance(other, VFraction)

	def merge(self, other):
		if not isinstance(other, VFraction):
			raise TypeError

	def _nd(self, builder):
		ssa_value = self.get_ssa_value(builder)
		numerator = builder.extract_element(ssa_value, lc.Constant.int(lc.Type.int(), 0))
		denominator = builder.extract_element(ssa_value, lc.Constant.int(lc.Type.int(), 1))
		return numerator, denominator

	def set_value_nd(self, builder, numerator, denominator):
		numerator = numerator.o_int64(builder).get_ssa_value(builder)
		denominator = denominator.o_int64(builder).get_ssa_value(builder)

		gcd_f = builder.module.get_function_named("__gcd64")
		gcd = builder.call(gcd_f, [numerator, denominator])
		numerator = builder.sdiv(numerator, gcd)
		denominator = builder.sdiv(denominator, gcd)

		value = lc.Constant.undef(lc.Type.vector(lc.Type.int(64), 2))
		value = builder.insert_element(value, numerator, lc.Constant.int(lc.Type.int(), 0))
		value = builder.insert_element(value, denominator, lc.Constant.int(lc.Type.int(), 1))
		self.set_ssa_value(builder, value)

	def set_value(self, builder, n):
		if not isinstance(n, VFraction):
			raise TypeError
		self.set_ssa_value(builder, n.get_ssa_value(builder))

	def o_bool(self, builder):
		r = VBool()
		if builder is not None:
			zero = lc.Constant.int(lc.Type.int(64), 0)
			numerator = builder.extract_element(self.get_ssa_value(builder), lc.Constant.int(lc.Type.int(), 0))
			r.set_ssa_value(builder, builder.icmp(lc.ICMP_NE, numerator, zero))
		return r

	def o_intx(self, target_bits, builder):
		if builder is None:
			return VInt(target_bits)
		else:
			r = VInt(64)
			numerator, denominator = self._nd(builder)
			r.set_ssa_value(builder, builder.sdiv(numerator, denominator))
			return r.o_intx(target_bits, builder)

	def o_roundx(self, target_bits, builder):
		if builder is None:
			return VInt(target_bits)
		else:
			r = VInt(64)
			numerator, denominator = self._nd(builder)
			h_denominator = builder.ashr(denominator, lc.Constant.int(lc.Type.int(), 1))
			r_numerator = builder.add(numerator, h_denominator)
			r.set_ssa_value(builder, builder.sdiv(r_numerator, denominator))
			return r.o_intx(target_bits, builder)

	def _o_eq_inv(self, other, builder, invert):
		if isinstance(other, VFraction):
			r = VBool()
			if builder is not None:
				ee = []
				for i in range(2):
					es = builder.extract_element(self.get_ssa_value(builder), lc.Constant.int(lc.Type.int(), i))
					eo = builder.extract_element(other.get_ssa_value(builder), lc.Constant.int(lc.Type.int(), i))
					ee.append(builder.icmp(lc.ICMP_EQ, es, eo))
				ssa_r = builder.and_(ee[0], ee[1])
				if invert:
					ssa_r = builder.xor(ssa_r, lc.Constant.int(lc.Type.int(1), 1))
				r.set_ssa_value(builder, ssa_r)
			return r
		else:
			return NotImplemented

	def o_eq(self, other, builder):
		return self._o_eq_inv(other, builder, False)

	def o_ne(self, other, builder):
		return self._o_eq_inv(other, builder, True)

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
				ropf = getattr(r, "or_"+op_name)
			except AttributeError:
				result = NotImplemented
			else:
				result = ropf(l, builder)
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

def init_module(module):
	func_type = lc.Type.function(lc.Type.int(64),
		[lc.Type.int(64), lc.Type.int(64)])
	module.add_function(func_type, "__gcd64")
