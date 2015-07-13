import inspect
import ast

import llvmlite_or1k.ir as ll

from artiq.py2llvm.values import VGeneric, operators
from artiq.py2llvm.base_types import VBool, VInt, VFloat


def _gcd(a, b):
    if a < 0:
        a = -a
    while a:
        c = a
        a = b % a
        b = c
    return b


def init_module(module):
    func_def = ast.parse(inspect.getsource(_gcd)).body[0]
    function, _ = module.compile_function(func_def,
                                          {"a": VInt(64), "b": VInt(64)})
    function.linkage = "internal"


def _reduce(builder, a, b):
    module = builder.basic_block.function.module
    for f in module.functions:
        if f.name == "_gcd":
            gcd_f = f
            break
    gcd = builder.call(gcd_f, [a, b])
    a = builder.sdiv(a, gcd)
    b = builder.sdiv(b, gcd)
    return a, b


def _signnum(builder, a, b):
    function = builder.basic_block.function
    orig_block = builder.basic_block
    swap_block = function.append_basic_block("sn_swap")
    merge_block = function.append_basic_block("sn_merge")

    condition = builder.icmp_signed(
        "<", b, ll.Constant(ll.IntType(64), 0))
    builder.cbranch(condition, swap_block, merge_block)

    builder.position_at_end(swap_block)
    minusone = ll.Constant(ll.IntType(64), -1)
    a_swp = builder.mul(minusone, a)
    b_swp = builder.mul(minusone, b)
    builder.branch(merge_block)

    builder.position_at_end(merge_block)
    a_phi = builder.phi(ll.IntType(64))
    a_phi.add_incoming(a, orig_block)
    a_phi.add_incoming(a_swp, swap_block)
    b_phi = builder.phi(ll.IntType(64))
    b_phi.add_incoming(b, orig_block)
    b_phi.add_incoming(b_swp, swap_block)

    return a_phi, b_phi


def _make_ssa(builder, n, d):
    value = ll.Constant(ll.ArrayType(ll.IntType(64), 2), ll.Undefined)
    value = builder.insert_value(value, n, 0)
    value = builder.insert_value(value, d, 1)
    return value


class VFraction(VGeneric):
    def get_llvm_type(self):
        return ll.ArrayType(ll.IntType(64), 2)

    def _nd(self, builder):
        ssa_value = self.auto_load(builder)
        a = builder.extract_value(ssa_value, 0)
        b = builder.extract_value(ssa_value, 1)
        return a, b

    def set_value_nd(self, builder, a, b):
        a = a.o_int64(builder).auto_load(builder)
        b = b.o_int64(builder).auto_load(builder)
        a, b = _reduce(builder, a, b)
        a, b = _signnum(builder, a, b)
        self.auto_store(builder, _make_ssa(builder, a, b))

    def set_value(self, builder, v):
        if not isinstance(v, VFraction):
            raise TypeError
        self.auto_store(builder, v.auto_load(builder))

    def o_getattr(self, attr, builder):
        if attr == "numerator":
            idx = 0
        elif attr == "denominator":
            idx = 1
        else:
            raise AttributeError
        r = VInt(64)
        if builder is not None:
            elt = builder.extract_value(self.auto_load(builder), idx)
            r.auto_store(builder, elt)
        return r

    def o_bool(self, builder):
        r = VBool()
        if builder is not None:
            zero = ll.Constant(ll.IntType(64), 0)
            a = builder.extract_element(self.auto_load(builder), 0)
            r.auto_store(builder, builder.icmp_signed("!=", a, zero))
        return r

    def o_intx(self, target_bits, builder):
        if builder is None:
            return VInt(target_bits)
        else:
            r = VInt(64)
            a, b = self._nd(builder)
            r.auto_store(builder, builder.sdiv(a, b))
            return r.o_intx(target_bits, builder)

    def o_roundx(self, target_bits, builder):
        if builder is None:
            return VInt(target_bits)
        else:
            r = VInt(64)
            a, b = self._nd(builder)
            h_b = builder.ashr(b, ll.Constant(ll.IntType(64), 1))

            function = builder.basic_block.function
            add_block = function.append_basic_block("fr_add")
            sub_block = function.append_basic_block("fr_sub")
            merge_block = function.append_basic_block("fr_merge")

            condition = builder.icmp_signed(
                "<", a, ll.Constant(ll.IntType(64), 0))
            builder.cbranch(condition, sub_block, add_block)

            builder.position_at_end(add_block)
            a_add = builder.add(a, h_b)
            builder.branch(merge_block)
            builder.position_at_end(sub_block)
            a_sub = builder.sub(a, h_b)
            builder.branch(merge_block)

            builder.position_at_end(merge_block)
            a = builder.phi(ll.IntType(64))
            a.add_incoming(a_add, add_block)
            a.add_incoming(a_sub, sub_block)
            r.auto_store(builder, builder.sdiv(a, b))
            return r.o_intx(target_bits, builder)

    def o_float(self, builder):
        r = VFloat()
        if builder is not None:
            a, b = self._nd(builder)
            af = builder.sitofp(a, r.get_llvm_type())
            bf = builder.sitofp(b, r.get_llvm_type())
            r.auto_store(builder, builder.fdiv(af, bf))
        return r

    def _o_eq_inv(self, other, builder, ne):
        if not isinstance(other, (VInt, VFraction)):
            return NotImplemented
        r = VBool()
        if builder is not None:
            if isinstance(other, VInt):
                other = other.o_int64(builder)
                a, b = self._nd(builder)
                ssa_r = builder.and_(
                    builder.icmp_signed("==", a,
                                        other.auto_load()),
                    builder.icmp_signed("==", b,
                                        ll.Constant(ll.IntType(64), 1)))
            else:
                a, b = self._nd(builder)
                c, d = other._nd(builder)
                ssa_r = builder.and_(
                    builder.icmp_signed("==", a, c),
                    builder.icmp_signed("==", b, d))
            if ne:
                ssa_r = builder.xor(ssa_r,
                                    ll.Constant(ll.IntType(1), 1))
            r.auto_store(builder, ssa_r)
        return r

    def o_eq(self, other, builder):
        return self._o_eq_inv(other, builder, False)

    def o_ne(self, other, builder):
        return self._o_eq_inv(other, builder, True)

    def _o_cmp(self, other, icmp, builder):
        diff = self.o_sub(other, builder)
        if diff is NotImplemented:
            return NotImplemented
        r = VBool()
        if builder is not None:
            diff = diff.auto_load(builder)
            a = builder.extract_value(diff, 0)
            zero = ll.Constant(ll.IntType(64), 0)
            ssa_r = builder.icmp_signed(icmp, a, zero)
            r.auto_store(builder, ssa_r)
        return r

    def o_lt(self, other, builder):
        return self._o_cmp(other, "<", builder)

    def o_le(self, other, builder):
        return self._o_cmp(other, "<=", builder)

    def o_gt(self, other, builder):
        return self._o_cmp(other, ">", builder)

    def o_ge(self, other, builder):
        return self._o_cmp(other, ">=", builder)

    def _o_addsub(self, other, builder, sub, invert=False):
        if isinstance(other, VFloat):
            a = self.o_getattr("numerator", builder)
            b = self.o_getattr("denominator", builder)
            if sub:
                if invert:
                    return operators.truediv(
                        operators.sub(operators.mul(other,
                                                    b,
                                                    builder),
                                      a,
                                      builder),
                        b,
                        builder)
                else:
                    return operators.truediv(
                        operators.sub(a,
                                      operators.mul(other,
                                                    b,
                                                    builder),
                                      builder),
                        b,
                        builder)
            else:
                return operators.truediv(
                    operators.add(operators.mul(other,
                                                b,
                                                builder),
                                  a,
                                  builder),
                    b,
                    builder)
        else:
            if not isinstance(other, (VFraction, VInt)):
                return NotImplemented
            r = VFraction()
            if builder is not None:
                if isinstance(other, VInt):
                    i = other.o_int64(builder).auto_load(builder)
                    x, rd = self._nd(builder)
                    y = builder.mul(rd, i)
                else:
                    a, b = self._nd(builder)
                    c, d = other._nd(builder)
                    rd = builder.mul(b, d)
                    x = builder.mul(a, d)
                    y = builder.mul(c, b)
                if sub:
                    if invert:
                        rn = builder.sub(y, x)
                    else:
                        rn = builder.sub(x, y)
                else:
                    rn = builder.add(x, y)
                rn, rd = _reduce(builder, rn, rd)  # rd is already > 0
                r.auto_store(builder, _make_ssa(builder, rn, rd))
            return r

    def o_add(self, other, builder):
        return self._o_addsub(other, builder, False)

    def o_sub(self, other, builder):
        return self._o_addsub(other, builder, True)

    def or_add(self, other, builder):
        return self._o_addsub(other, builder, False)

    def or_sub(self, other, builder):
        return self._o_addsub(other, builder, True, True)

    def _o_muldiv(self, other, builder, div, invert=False):
        if isinstance(other, VFloat):
            a = self.o_getattr("numerator", builder)
            b = self.o_getattr("denominator", builder)
            if invert:
                a, b = b, a
            if div:
                return operators.truediv(a,
                                         operators.mul(b, other, builder),
                                         builder)
            else:
                return operators.truediv(operators.mul(a, other, builder),
                                         b,
                                         builder)
        else:
            if not isinstance(other, (VFraction, VInt)):
                return NotImplemented
            r = VFraction()
            if builder is not None:
                a, b = self._nd(builder)
                if invert:
                    a, b = b, a
                if isinstance(other, VInt):
                    i = other.o_int64(builder).auto_load(builder)
                    if div:
                        b = builder.mul(b, i)
                    else:
                        a = builder.mul(a, i)
                else:
                    c, d = other._nd(builder)
                    if div:
                        a = builder.mul(a, d)
                        b = builder.mul(b, c)
                    else:
                        a = builder.mul(a, c)
                        b = builder.mul(b, d)
                if div or invert:
                    a, b = _signnum(builder, a, b)
                a, b = _reduce(builder, a, b)
                r.auto_store(builder, _make_ssa(builder, a, b))
            return r

    def o_mul(self, other, builder):
        return self._o_muldiv(other, builder, False)

    def o_truediv(self, other, builder):
        return self._o_muldiv(other, builder, True)

    def or_mul(self, other, builder):
        return self._o_muldiv(other, builder, False)

    def or_truediv(self, other, builder):
        # multiply by the inverse
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
