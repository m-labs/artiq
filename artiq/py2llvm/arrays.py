from llvm import core as lc

from artiq.py2llvm.values import VGeneric
from artiq.py2llvm.base_types import VInt


class VArray(VGeneric):
    def __init__(self, el_init, count):
        VGeneric.__init__(self)
        self.el_init = el_init
        self.count = count
        if not count:
            raise TypeError("Arrays must have at least one element")

    def get_llvm_type(self):
        return lc.Type.array(self.el_init.get_llvm_type(), self.count)

    def __repr__(self):
        return "<VArray:{} x{}>".format(repr(self.el_init), self.count)

    def same_type(self, other):
        return (
            isinstance(other, VArray)
            and self.el_init.same_type(other.el_init)
            and self.count == other.count)

    def merge(self, other):
        if isinstance(other, VArray):
            self.el_init.merge(other.el_init)
        else:
            raise TypeError("Incompatible types: {} and {}"
                            .format(repr(self), repr(other)))

    def merge_subscript(self, other):
        self.el_init.merge(other)

    def set_value(self, builder, v):
        if not isinstance(v, VArray):
            raise TypeError
        if v.llvm_value is not None:
            raise NotImplementedError("Array aliasing is not supported")

        i = VInt()
        i.alloca(builder, "ai_i")
        i.auto_store(builder, lc.Constant.int(lc.Type.int(), 0))

        function = builder.basic_block.function
        copy_block = function.append_basic_block("ai_copy")
        end_block = function.append_basic_block("ai_end")
        builder.branch(copy_block)

        builder.position_at_end(copy_block)
        self.o_subscript(i, builder).set_value(builder, v.el_init)
        i.auto_store(builder, builder.add(
            i.auto_load(builder), lc.Constant.int(lc.Type.int(), 1)))
        cont = builder.icmp(
            lc.ICMP_SLT, i.auto_load(builder),
            lc.Constant.int(lc.Type.int(), self.count))
        builder.cbranch(cont, copy_block, end_block)

        builder.position_at_end(end_block)

    def o_subscript(self, index, builder):
        r = self.el_init.new()
        if builder is not None:
            index = index.o_int(builder).auto_load(builder)
            ssa_r = builder.gep(self.llvm_value, [
                lc.Constant.int(lc.Type.int(), 0), index])
            r.auto_store(builder, ssa_r)
        return r
