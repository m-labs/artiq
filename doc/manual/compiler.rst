Compiler
========

The ARTIQ compiler transforms the Python code of the kernels into machine code executable on the core device. It is invoked automatically when calling a function that uses the ``@kernel`` decorator.

Supported Python features
-------------------------

A number of Python features can be used inside a kernel for compilation and execution on the core device. They include ``for`` and ``while`` loops, conditionals (``if``, ``else``, ``elif``), functions, exceptions, and statically typed variables of the following types:

* Booleans
* 32-bit signed integers (default size)
* 64-bit signed integers (use ``int(n, width=64)`` to convert)
* Double-precision floating point numbers
* Lists of the above types.

For a demonstration of some of these features, see the ``mandelbrot.py`` example.

Additional optimizations
------------------------

The ARTIQ compiler runs many optimizations, most of which perform well on code that has pristine Python semantics. It also contains more powerful, and more invasive, optimizations that require opt-in to activate.

Fast-math flags
+++++++++++++++

The compiler does not normally perform algebraically equivalent transformations on floating-point expressions, because this can dramatically change the result. However, it can be instructed to do so if all of the following is true:

* Arguments and results will not be not-a-number or infinity values;
* The sign of a zero value is insignificant;
* Any algebraically equivalent transformations, such as reassociation or replacing division with multiplication by reciprocal, are legal to perform.

If this is the case for a given kernel, a ``fast-math`` flag can be specified to enable more aggressive optimization for this specific kernel: ::

    @kernel(flags={"fast-math"})
    def calculate(x, y, z):
        return x * z + y * z

This flag particularly benefits loops with I/O delays performed in fractional seconds rather than machine units, as well as updates to DDS phase and frequency.

Kernel invariants
+++++++++++++++++

The compiler attempts to remove or hoist out of loops any redundant memory load operations, as well as propagate known constants into function bodies, which can enable further optimization. However, it must make conservative assumptions about code that it is unable to observe, because such code can change the value of the attribute, making the optimization invalid.

When an attribute is known to never change while the kernel is running, it can be marked as a *kernel invariant* to enable more aggressive optimization for this specific attribute: ::

    class Converter:
        kernel_invariants = {"ratio"}

        def __init__(self, ratio=1.0):
            self.ratio = ratio

        @kernel
        def convert(self, value):
            return value * self.ratio ** 2

In the synthetic example above, the compiler will be able to detect that the result of evaluating ``self.ratio ** 2`` never changes and replace it with a constant, removing an expensive floating-point operation.
