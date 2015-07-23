import llvmlite_or1k.ir as ll

from artiq.py2llvm.values import VGeneric
from artiq.py2llvm.base_types import VInt, VNone


class VList(VGeneric):
    def __init__(self, el_type, alloc_count):
        VGeneric.__init__(self)
        self.el_type = el_type
        self.alloc_count = alloc_count

    def get_llvm_type(self):
        count = 0 if self.alloc_count is None else self.alloc_count
        if isinstance(self.el_type, VNone):
            return ll.LiteralStructType([ll.IntType(32)])
        else:
            return ll.LiteralStructType([
                ll.IntType(32), ll.ArrayType(self.el_type.get_llvm_type(),
                                             count)])

    def __repr__(self):
        return "<VList:{} x{}>".format(
            repr(self.el_type),
            "?" if self.alloc_count is None else self.alloc_count)

    def same_type(self, other):
        return (isinstance(other, VList)
                and self.el_type.same_type(other.el_type))

    def merge(self, other):
        if isinstance(other, VList):
            if self.alloc_count:
                if other.alloc_count:
                    self.el_type.merge(other.el_type)
                    if self.alloc_count < other.alloc_count:
                        self.alloc_count = other.alloc_count
            else:
                self.el_type = other.el_type.new()
                self.alloc_count = other.alloc_count
        else:
            raise TypeError("Incompatible types: {} and {}"
                            .format(repr(self), repr(other)))

    def merge_subscript(self, other):
        self.el_type.merge(other)

    def set_count(self, builder, count):
        count_ptr = builder.gep(self.llvm_value, [
            ll.Constant(ll.IntType(32), 0),
            ll.Constant(ll.IntType(32), 0)])
        builder.store(ll.Constant(ll.IntType(32), count), count_ptr)

    def o_len(self, builder):
        r = VInt()
        if builder is not None:
            count_ptr = builder.gep(self.llvm_value, [
                ll.Constant(ll.IntType(32), 0),
                ll.Constant(ll.IntType(32), 0)])
            r.auto_store(builder, builder.load(count_ptr))
        return r

    def o_subscript(self, index, builder):
        r = self.el_type.new()
        if builder is not None and not isinstance(r, VNone):
            index = index.o_int(builder).auto_load(builder)
            ssa_r = builder.gep(self.llvm_value, [
                ll.Constant(ll.IntType(32), 0),
                ll.Constant(ll.IntType(32), 1),
                index])
            r.auto_store(builder, ssa_r)
        return r
