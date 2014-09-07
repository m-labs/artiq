from llvm import core as lc

from artiq.py2llvm.values import VGeneric


class VNone(VGeneric):
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
            raise TypeError

    def set_value(self, builder, n):
        self.set_ssa_value(
            builder, n.o_intx(self.nbits, builder).get_ssa_value(builder))

    def set_const_value(self, builder, n):
        self.set_ssa_value(builder, lc.Constant.int(self.get_llvm_type(), n))

    def o_bool(self, builder, inv=False):
        r = VBool()
        if builder is not None:
            r.set_ssa_value(
                builder, builder.icmp(
                    lc.ICMP_EQ if inv else lc.ICMP_NE,
                    self.get_ssa_value(builder),
                    lc.Constant.int(self.get_llvm_type(), 0)))
        return r

    def o_not(self, builder):
        return self.o_bool(builder, True)

    def o_intx(self, target_bits, builder):
        r = VInt(target_bits)
        if builder is not None:
            if self.nbits == target_bits:
                r.set_ssa_value(
                    builder, self.get_ssa_value(builder))
            if self.nbits > target_bits:
                r.set_ssa_value(
                    builder, builder.trunc(self.get_ssa_value(builder),
                                           r.get_llvm_type()))
            if self.nbits < target_bits:
                r.set_ssa_value(
                    builder, builder.sext(self.get_ssa_value(builder),
                                          r.get_llvm_type()))
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
                    r.set_ssa_value(
                        builder, bf(left.get_ssa_value(builder),
                                    right.get_ssa_value(builder)))
                return r
            else:
                return NotImplemented
    return binop_method

for _method_name, _builder_name in (("o_add", "add"),
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
                r.set_ssa_value(
                    builder,
                    builder.icmp(
                        icmp_val, left.get_ssa_value(builder),
                        right.get_ssa_value(builder)))
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
