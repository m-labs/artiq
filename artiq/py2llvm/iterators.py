from llvm import core as lc

from artiq.py2llvm.values import operators
from artiq.py2llvm.base_types import VBool, VInt

class IRange:
    def __init__(self, builder, args):
        minimum, step = None, None
        if len(args) == 1:
            maximum = args[0]
        elif len(args) == 2:
            minimum, maximum = args
        else:
            minimum, maximum, step = args
        if minimum is None:
            minimum = VInt()
            if builder is not None:
                minimum.set_const_value(builder, 0)
        if step is None:
            step = VInt()
            if builder is not None:
                step.set_const_value(builder, 1)

        self._counter = minimum.new()
        self._counter.merge(maximum)
        self._counter.merge(step)
        self._minimum = self._counter.new()
        self._maximum = self._counter.new()
        self._step = self._counter.new()

        if builder is not None:
            self._minimum.alloca(builder, "irange_min")
            self._maximum.alloca(builder, "irange_max")
            self._step.alloca(builder, "irange_step")
            self._counter.alloca(builder, "irange_count")

            self._minimum.set_value(builder, minimum)
            self._maximum.set_value(builder, maximum)
            self._step.set_value(builder, step)

            counter_init = operators.sub(self._minimum, self._step, builder)
            self._counter.set_value(builder, counter_init)

    # must be a pointer value that can be dereferenced anytime
    # to get the current value of the iterator
    def get_value_ptr(self):
        return self._counter

    def o_next(self, builder):
        self._counter.set_value(
            builder,
            operators.add(self._counter, self._step, builder))
        return operators.lt(self._counter, self._maximum, builder)
