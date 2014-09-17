from llvm import core as lc

from artiq.py2llvm.values import VGeneric


class VNone(VGeneric):
    def get_llvm_type(self):
        return lc.Type.void()

    def alloca(self, builder, name):
        pass

    def o_bool(self, builder):
        r = VBool()
        if builder is not None:
            r.set_const_value(builder, False)
        return r

    def o_not(self, builder):
        r = VBool()
        if builder is not None:
            r.set_const_value(builder, True)
        return r


class VInt(VGeneric):
    def __init__(self, nbits=32):
        VGeneric.__init__(self)
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
            raise TypeError("Incompatible types: {} and {}"
                            .format(repr(self), repr(other)))

    def set_value(self, builder, n):
        self.auto_store(
            builder, n.o_intx(self.nbits, builder).auto_load(builder))

    def set_const_value(self, builder, n):
        self.auto_store(builder, lc.Constant.int(self.get_llvm_type(), n))

    def o_bool(self, builder, inv=False):
        r = VBool()
        if builder is not None:
            r.auto_store(
                builder, builder.icmp(
                    lc.ICMP_EQ if inv else lc.ICMP_NE,
                    self.auto_load(builder),
                    lc.Constant.int(self.get_llvm_type(), 0)))
        return r

    def o_float(self, builder):
        r = VFloat()
        if builder is not None:
            if isinstance(self, VBool):
                cf = builder.uitofp
            else:
                cf = builder.sitofp
            r.auto_store(builder, cf(self.auto_load(builder),
                                     r.get_llvm_type()))
        return r

    def o_not(self, builder):
        return self.o_bool(builder, True)

    def o_neg(self, builder):
        r = VInt(self.nbits)
        if builder is not None:
            r.auto_store(
                builder, builder.mul(
                    self.auto_load(builder),
                    lc.Constant.int(self.get_llvm_type(), -1)))
        return r

    def o_intx(self, target_bits, builder):
        r = VInt(target_bits)
        if builder is not None:
            if self.nbits == target_bits:
                r.auto_store(
                    builder, self.auto_load(builder))
            if self.nbits > target_bits:
                r.auto_store(
                    builder, builder.trunc(self.auto_load(builder),
                                           r.get_llvm_type()))
            if self.nbits < target_bits:
                if isinstance(self, VBool):
                    ef = builder.zext
                else:
                    ef = builder.sext
                r.auto_store(
                    builder, ef(self.auto_load(builder),
                                          r.get_llvm_type()))
        return r
    o_roundx = o_intx

    def o_truediv(self, other, builder):
        if isinstance(other, VInt):
            left = self.o_float(builder)
            right = other.o_float(builder)
            return left.o_truediv(right, builder)
        else:
            return NotImplemented

def _make_vint_binop_method(builder_name, bool_op):
    def binop_method(self, other, builder):
        if isinstance(other, VInt):
            target_bits = max(self.nbits, other.nbits)
            if not bool_op and target_bits == 1:
                target_bits = 32
            if bool_op and target_bits == 1:
                r = VBool()
            else:
                r = VInt(target_bits)
            if builder is not None:
                left = self.o_intx(target_bits, builder)
                right = other.o_intx(target_bits, builder)
                bf = getattr(builder, builder_name)
                r.auto_store(
                    builder, bf(left.auto_load(builder),
                                right.auto_load(builder)))
            return r
        else:
            return NotImplemented
    return binop_method

for _method_name, _builder_name, _bool_op in (("o_add", "add", False),
                                              ("o_sub", "sub", False),
                                              ("o_mul", "mul", False),
                                              ("o_floordiv", "sdiv", False),
                                              ("o_mod", "srem", False),
                                              ("o_and", "and_", True),
                                              ("o_xor", "xor", True),
                                              ("o_or", "or_", True)):
    setattr(VInt, _method_name, _make_vint_binop_method(_builder_name, _bool_op))


def _make_vint_cmp_method(icmp_val):
    def cmp_method(self, other, builder):
        if isinstance(other, VInt):
            r = VBool()
            if builder is not None:
                target_bits = max(self.nbits, other.nbits)
                left = self.o_intx(target_bits, builder)
                right = other.o_intx(target_bits, builder)
                r.auto_store(
                    builder,
                    builder.icmp(
                        icmp_val, left.auto_load(builder),
                        right.auto_load(builder)))
            return r
        else:
            return NotImplemented
    return cmp_method

for _method_name, _icmp_val in (("o_eq", lc.ICMP_EQ),
                                ("o_ne", lc.ICMP_NE),
                                ("o_lt", lc.ICMP_SLT),
                                ("o_le", lc.ICMP_SLE),
                                ("o_gt", lc.ICMP_SGT),
                                ("o_ge", lc.ICMP_SGE)):
    setattr(VInt, _method_name, _make_vint_cmp_method(_icmp_val))


class VBool(VInt):
    def __init__(self):
        VInt.__init__(self, 1)

    __repr__ = VGeneric.__repr__
    same_type = VGeneric.same_type
    merge = VGeneric.merge

    def set_const_value(self, builder, b):
        VInt.set_const_value(self, builder, int(b))

    def o_bool(self, builder):
        r = VBool()
        if builder is not None:
            r.auto_store(builder, self.auto_load(builder))
        return r


class VFloat(VGeneric):
    def get_llvm_type(self):
        return lc.Type.double()

    def set_value(self, builder, v):
        if not isinstance(v, VFloat):
            raise TypeError
        self.auto_store(builder, v.auto_load(builder))

    def set_const_value(self, builder, n):
        self.auto_store(builder, lc.Constant.real(self.get_llvm_type(), n))

    def o_float(self, builder):
        r = VFloat()
        if builder is not None:
            r.auto_store(builder, self.auto_load(builder))
        return r

    def o_bool(self, builder, inv=False):
        r = VBool()
        if builder is not None:
            r.auto_store(
                builder, builder.fcmp(
                    lc.FCMP_UEQ if inv else lc.FCMP_UNE,
                    self.auto_load(builder),
                    lc.Constant.real(self.get_llvm_type(), 0.0)))
        return r

    def o_not(self, builder):
        return self.o_bool(builder, True)

    def o_neg(self, builder):
        r = VFloat()
        if builder is not None:
            r.auto_store(
                builder, builder.fmul(
                    self.auto_load(builder),
                    lc.Constant.real(self.get_llvm_type(), -1.0)))
        return r

    def o_intx(self, target_bits, builder):
        r = VInt(target_bits)
        if builder is not None:
            r.auto_store(builder, builder.fptosi(self.auto_load(builder),
                                                 r.get_llvm_type()))
        return r

    def o_roundx(self, target_bits, builder):
        r = VInt(target_bits)
        if builder is not None:
            function = builder.basic_block.function
            neg_block = function.append_basic_block("fr_neg")
            merge_block = function.append_basic_block("fr_merge")

            half = VFloat()
            half.alloca(builder, "half")
            half.set_const_value(builder, 0.5)

            condition = builder.icmp(
                lc.FCMP_OLT,
                self.auto_load(builder),
                lc.Constant.real(self.get_llvm_type(), 0.0))
            builder.cbranch(condition, neg_block, merge_block)

            builder.position_at_end(neg_block)
            half.set_const_value(builder, -0.5)
            builder.branch(merge_block)

            builder.position_at_end(merge_block)
            s = builder.fadd(self.auto_load(builder), half.auto_load(builder))
            r.auto_store(builder, builder.fptosi(s, r.get_llvm_type()))
        return r

    def o_floordiv(self, other, builder):
        return self.o_truediv(other, builder).o_int64(builder).o_float(builder)

def _make_vfloat_binop_method(builder_name, reverse):
    def binop_method(self, other, builder):
        if not hasattr(other, "o_float"):
            return NotImplemented
        r = VFloat()
        if builder is not None:
            left = self.o_float(builder)
            right = other.o_float(builder)
            if reverse:
                left, right = right, left
            bf = getattr(builder, builder_name)
            r.auto_store(
                builder, bf(left.auto_load(builder),
                            right.auto_load(builder)))
        return r
    return binop_method

for _method_name, _builder_name in (("add", "fadd"),
                                    ("sub", "fsub"),
                                    ("mul", "fmul"),
                                    ("truediv", "fdiv")):
    setattr(VFloat, "o_" + _method_name,
            _make_vfloat_binop_method(_builder_name, False))
    setattr(VFloat, "or_" + _method_name,
            _make_vfloat_binop_method(_builder_name, True))


def _make_vfloat_cmp_method(fcmp_val):
    def cmp_method(self, other, builder):
        if not hasattr(other, "o_float"):
            return NotImplemented
        r = VBool()
        if builder is not None:
            left = self.o_float(builder)
            right = other.o_float(builder)
            r.auto_store(
                builder,
                builder.fcmp(
                    fcmp_val, left.auto_load(builder),
                    right.auto_load(builder)))
        return r
    return cmp_method

for _method_name, _fcmp_val in (("o_eq", lc.FCMP_OEQ),
                                ("o_ne", lc.FCMP_ONE),
                                ("o_lt", lc.FCMP_OLT),
                                ("o_le", lc.FCMP_OLE),
                                ("o_gt", lc.FCMP_OGT),
                                ("o_ge", lc.FCMP_OGE)):
    setattr(VFloat, _method_name, _make_vfloat_cmp_method(_fcmp_val))
