from types import SimpleNamespace
from copy import copy

import llvmlite_or1k.ir as ll


class VGeneric:
    def __init__(self):
        self.llvm_value = None

    def new(self):
        r = copy(self)
        r.llvm_value = None
        return r

    def __repr__(self):
        return "<" + self.__class__.__name__ + ">"

    def same_type(self, other):
        return isinstance(other, self.__class__)

    def merge(self, other):
        if not self.same_type(other):
            raise TypeError("Incompatible types: {} and {}"
                            .format(repr(self), repr(other)))

    def auto_load(self, builder):
        if isinstance(self.llvm_value.type, ll.PointerType):
            return builder.load(self.llvm_value)
        else:
            return self.llvm_value

    def auto_store(self, builder, llvm_value):
        if self.llvm_value is None:
            self.llvm_value = llvm_value
        elif isinstance(self.llvm_value.type, ll.PointerType):
            builder.store(llvm_value, self.llvm_value)
        else:
            raise RuntimeError(
                "Attempted to set LLVM SSA value multiple times")

    def alloca(self, builder, name=""):
        if self.llvm_value is not None:
            raise RuntimeError("Attempted to alloca existing LLVM value "+name)
        self.llvm_value = builder.alloca(self.get_llvm_type(), name=name)

    def o_int(self, builder):
        return self.o_intx(32, builder)

    def o_int64(self, builder):
        return self.o_intx(64, builder)

    def o_round(self, builder):
        return self.o_roundx(32, builder)

    def o_round64(self, builder):
        return self.o_roundx(64, builder)


def _make_binary_operator(op_name):
    def op(l, r, builder):
        try:
            opf = getattr(l, "o_" + op_name)
        except AttributeError:
            result = NotImplemented
        else:
            result = opf(r, builder)
        if result is NotImplemented:
            try:
                ropf = getattr(r, "or_" + op_name)
            except AttributeError:
                result = NotImplemented
            else:
                result = ropf(l, builder)
            if result is NotImplemented:
                raise TypeError(
                    "Unsupported operand types for {}: {} and {}"
                    .format(op_name, type(l).__name__, type(r).__name__))
        return result
    return op


def _make_operators():
    d = dict()
    for op_name in ("add", "sub", "mul",
                    "truediv", "floordiv", "mod",
                    "pow", "lshift", "rshift", "xor",
                    "eq", "ne", "lt", "le", "gt", "ge"):
        d[op_name] = _make_binary_operator(op_name)
    d["and_"] = _make_binary_operator("and")
    d["or_"] = _make_binary_operator("or")
    return SimpleNamespace(**d)

operators = _make_operators()
