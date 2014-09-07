from types import SimpleNamespace

from llvm import core as lc


class VGeneric:
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
            raise RuntimeError(
                "Attempted to set LLVM SSA value multiple times")

    def alloca(self, builder, name):
        if self._llvm_value is not None:
            raise RuntimeError("Attempted to alloca existing LLVM value "+name)
        self._llvm_value = builder.alloca(self.get_llvm_type(), name=name)

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
