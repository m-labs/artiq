from llvm import core as lc

from artiq.py2llvm.values import VGeneric
from artiq.py2llvm.base_types import VBool, VInt


def _gcd64(builder, a, b):
    gcd_f = builder.basic_block.function.module.get_function_named("__gcd64")
    return builder.call(gcd_f, [a, b])

def init_module(module):
    func_type = lc.Type.function(
        lc.Type.int(64), [lc.Type.int(64), lc.Type.int(64)])
    module.add_function(func_type, "__gcd64")


def _frac_normalize(builder, numerator, denominator):
    gcd = _gcd64(builder, numerator, denominator)
    numerator = builder.sdiv(numerator, gcd)
    denominator = builder.sdiv(denominator, gcd)
    return numerator, denominator


def _frac_make_ssa(builder, numerator, denominator):
    value = lc.Constant.undef(lc.Type.vector(lc.Type.int(64), 2))
    value = builder.insert_element(
        value, numerator, lc.Constant.int(lc.Type.int(), 0))
    value = builder.insert_element(
        value, denominator, lc.Constant.int(lc.Type.int(), 1))
    return value


class VFraction(VGeneric):
    def get_llvm_type(self):
        return lc.Type.vector(lc.Type.int(64), 2)

    def __repr__(self):
        return "<VFraction>"

    def same_type(self, other):
        return isinstance(other, VFraction)

    def merge(self, other):
        if not isinstance(other, VFraction):
            raise TypeError

    def _nd(self, builder, invert=False):
        ssa_value = self.get_ssa_value(builder)
        numerator = builder.extract_element(
            ssa_value, lc.Constant.int(lc.Type.int(), 0))
        denominator = builder.extract_element(
            ssa_value, lc.Constant.int(lc.Type.int(), 1))
        if invert:
            return denominator, numerator
        else:
            return numerator, denominator

    def set_value_nd(self, builder, numerator, denominator):
        numerator = numerator.o_int64(builder).get_ssa_value(builder)
        denominator = denominator.o_int64(builder).get_ssa_value(builder)
        numerator, denominator = _frac_normalize(
            builder, numerator, denominator)
        self.set_ssa_value(
            builder, _frac_make_ssa(builder, numerator, denominator))

    def set_value(self, builder, n):
        if not isinstance(n, VFraction):
            raise TypeError
        self.set_ssa_value(builder, n.get_ssa_value(builder))

    def o_bool(self, builder):
        r = VBool()
        if builder is not None:
            zero = lc.Constant.int(lc.Type.int(64), 0)
            numerator = builder.extract_element(
                self.get_ssa_value(builder), lc.Constant.int(lc.Type.int(), 0))
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
            h_denominator = builder.ashr(denominator,
                                         lc.Constant.int(lc.Type.int(), 1))
            r_numerator = builder.add(numerator, h_denominator)
            r.set_ssa_value(builder, builder.sdiv(r_numerator, denominator))
            return r.o_intx(target_bits, builder)

    def _o_eq_inv(self, other, builder, ne):
        if isinstance(other, VFraction):
            r = VBool()
            if builder is not None:
                ee = []
                for i in range(2):
                    es = builder.extract_element(
                        self.get_ssa_value(builder),
                        lc.Constant.int(lc.Type.int(), i))
                    eo = builder.extract_element(
                        other.get_ssa_value(builder),
                        lc.Constant.int(lc.Type.int(), i))
                    ee.append(builder.icmp(lc.ICMP_EQ, es, eo))
                ssa_r = builder.and_(ee[0], ee[1])
                if ne:
                    ssa_r = builder.xor(ssa_r,
                                        lc.Constant.int(lc.Type.int(1), 1))
                r.set_ssa_value(builder, ssa_r)
            return r
        else:
            return NotImplemented

    def o_eq(self, other, builder):
        return self._o_eq_inv(other, builder, False)

    def o_ne(self, other, builder):
        return self._o_eq_inv(other, builder, True)

    def _o_muldiv(self, other, builder, div, invert=False):
        r = VFraction()
        if isinstance(other, VInt):
            if builder is None:
                return r
            else:
                numerator, denominator = self._nd(builder, invert)
                i = other.get_ssa_value(builder)
                if div:
                    gcd = _gcd64(i, numerator)
                    i = builder.sdiv(i, gcd)
                    numerator = builder.sdiv(numerator, gcd)
                    denominator = builder.mul(denominator, i)
                else:
                    gcd = _gcd64(i, denominator)
                    i = builder.sdiv(i, gcd)
                    denominator = builder.sdiv(denominator, gcd)
                    numerator = builder.mul(numerator, i)
                self.set_ssa_value(builder, _frac_make_ssa(builder, numerator,
                                                           denominator))
        elif isinstance(other, VFraction):
            if builder is None:
                return r
            else:
                numerator, denominator = self._nd(builder, invert)
                onumerator, odenominator = other._nd(builder)
                if div:
                    numerator = builder.mul(numerator, odenominator)
                    denominator = builder.mul(denominator, onumerator)
                else:
                    numerator = builder.mul(numerator, onumerator)
                    denominator = builder.mul(denominator, odenominator)
                numerator, denominator = _frac_normalize(builder, numerator,
                                                         denominator)
                self.set_ssa_value(
                    builder, _frac_make_ssa(builder, numerator, denominator))
        else:
            return NotImplemented

    def o_mul(self, other, builder):
        return self._o_muldiv(other, builder, False)

    def o_truediv(self, other, builder):
        return self._o_muldiv(other, builder, True)

    def or_mul(self, other, builder):
        return self._o_muldiv(other, builder, False)

    def or_truediv(self, other, builder):
        return self._o_muldiv(other, builder, False, True)

    def o_floordiv(self, other, builder):
        r = self.o_truediv(other, builder)
        if r is NotImplemented:
            return r
        else:
            return r.o_int(builder)

    def or_floordiv(self, other, builder):
        r = self.or_truediv(other, builder)
        if r is NotImplemented:
            return r
        else:
            return r.o_int(builder)
