Compiler
========

The ARTIQ compiler transforms the Python code of the kernels into machine code executable on the core device. It is invoked automatically when calling a function that uses the ``@kernel`` decorator.

Supported Python features
-------------------------

A number of Python features can be used inside a kernel for compilation and execution on the core device. They include ``for`` and ``while`` loops, conditionals (``if``, ``else``, ``elif``), functions, exceptions, and statically typed variables of the following types:

* Booleans
* 32-bit signed integers (default size)
* 64-bit signed integers (use ``numpy.int64`` to convert)
* Double-precision floating point numbers
* Lists of any supported types
* String constants
* User-defined classes, with attributes of any supported types (attributes that are not used anywhere in the kernel are ignored)

For a demonstration of some of these features, see the ``mandelbrot.py`` example.

When several instances of a user-defined class are referenced from the same kernel, every attribute must have the same type in every instance of the class.

Remote procedure calls
----------------------

Kernel code can call host functions without any additional ceremony. However, such functions are assumed to return `None`, and if a value other than `None` is returned, an exception is raised. To call a host function returning a value other than `None` its return type must be annotated using the standard Python syntax, e.g.: ::

    def return_four() -> TInt32:
        return 4

The Python types correspond to ARTIQ type annotations as follows:

+---------------+-------------------------+
| Python        | ARTIQ                   |
+===============+=========================+
| NoneType      | TNone                   |
+---------------+-------------------------+
| bool          | TBool                   |
+---------------+-------------------------+
| int           | TInt32 or TInt64        |
+---------------+-------------------------+
| float         | TFloat                  |
+---------------+-------------------------+
| str           | TStr                    |
+---------------+-------------------------+
| list of T     | TList(T)                |
+---------------+-------------------------+
| range         | TRange32, TRange64      |
+---------------+-------------------------+
| numpy.int32   | TInt32                  |
+---------------+-------------------------+
| numpy.int64   | TInt64                  |
+---------------+-------------------------+
| numpy.float64 | TFloat                  |
+---------------+-------------------------+

Pitfalls
--------

The ARTIQ compiler accepts *nearly* a strict subset of Python 3. However, by necessity there
is a number of differences that can lead to bugs.

Arbitrary-length integers are not supported at all on the core device; all integers are
either 32-bit or 64-bit. This especially affects calculations that result in a 32-bit signed
overflow; if the compiler detects a constant that doesn't fit into 32 bits, the entire expression
will be upgraded to 64-bit arithmetics, however if all constants are small, 32-bit arithmetics
will be used even if the result will overflow. Overflows are not detected.

The result of calling the builtin ``round`` function is different when used with
the builtin ``float`` type and the ``numpy.float64`` type on the host interpreter; ``round(1.0)``
returns an integer value 1, whereas ``round(numpy.float64(1.0))`` returns a floating point value
``numpy.float64(1.0)``. Since both ``float`` and ``numpy.float64`` are mapped to
the builtin ``float`` type on the core device, this can lead to problems in functions marked
``@portable``; the workaround is to explicitly cast the argument of ``round`` to ``float``:
``round(float(numpy.float64(1.0)))`` returns an integer on the core device as well as on the host
interpreter.

Asynchronous RPCs
-----------------

If an RPC returns no value, it can be invoked in a way that does not block until the RPC finishes
execution, but only until it is queued. (Submitting asynchronous RPCs too rapidly, as well as
submitting asynchronous RPCs with arguments that are too large, can still block until completion.)

To define an asynchronous RPC, use the ``@rpc`` annotation with a flag: ::

    @rpc(flags={"async"})
    def record_result(x):
        self.results.append(x)

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

When an attribute is known to never change while the kernel is running, it can be marked as a *kernel invariant* to enable more aggressive optimization for this specific attribute. ::

    class Converter:
        kernel_invariants = {"ratio"}

        def __init__(self, ratio=1.0):
            self.ratio = ratio

        @kernel
        def convert(self, value):
            return value * self.ratio ** 2

In the synthetic example above, the compiler will be able to detect that the result of evaluating ``self.ratio ** 2`` never changes and replace it with a constant, removing an expensive floating-point operation. ::

    class Worker:
        kernel_invariants = {"interval"}

        def __init__(self, interval=1.0*us):
            self.interval = interval

        def work(self):
            # something useful

    class Looper:
        def __init__(self, worker):
            self.worker = worker

        @kernel
        def loop(self):
            for _ in range(100):
                delay(self.worker.interval / 5.0)
                self.worker.work()

In the synthetic example above, the compiler will be able to detect that the result of evaluating ``self.interval / 5.0`` never changes, even though it neither knows the value of ``self.worker.interval`` beforehand nor can it see through the ``self.worker.work()`` function call, and hoist the expensive floating-point division out of the loop, transforming the code for ``loop`` into an equivalent of the following: ::

        @kernel
        def loop(self):
            precomputed_delay_mu = self.core.seconds_to_mu(self.worker.interval / 5.0)
            for _ in range(100):
                delay_mu(precomputed_delay_mu)
                self.worker.work()
