Compiler
========

The ARTIQ compiler transforms the Python code of the kernels into machine code executable on the core device. For limited purposes (normally, obtaining executable binaries of idle and startup kernels), it can be accessed through :mod:`~artiq.frontend.artiq_compile`. Otherwise it is invoked automatically whenever a function with an applicable decorator is called.

ARTIQ kernel code accepts *nearly,* but not quite, a strict subset of Python 3. The necessities of real-time operation impose a harsher set of limitations; as a result, many Python features are necessarily omitted, and there are some specific discrepancies (see also :ref:`compiler-pitfalls`).

In general, ARTIQ Python supports only statically typed variables; it implements no heap allocation or garbage collection systems, essentially disallowing any heap-based data structures (although lists and arrays remain available in a stack-based form); and it cannot use runtime dispatch, meaning that, for example, all elements of an array must be of the same type. Nonetheless, technical details aside, a basic knowledge of Python is entirely sufficient to write ARTIQ experiments.

.. note::
    The ARTIQ compiler is now in its second iteration. The third generation, known as NAC3, is `currently in development <https://git.m-labs.hk/M-Labs/nac3>`_, and available for pre-alpha experimental use. NAC3 represents a major overhaul of ARTIQ compilation, and will feature much faster compilation speeds, a greatly improved type system, and more predictable and transparent operation. It is compatible with ARTIQ firmware starting at ARTIQ-7. Instructions for installation and basic usage differences can also be found `on the M-Labs Forum <https://forum.m-labs.hk/d/392-nac3-new-artiq-compiler-3-prealpha-release>`_. While NAC3 is a work in progress and many important features remain unimplemented, installation and feedback is welcomed.

ARTIQ Python code
-----------------

A variety of short experiments can be found in the subfolders of ``artiq/examples``, especially under ``kc705_nist_clock/repository`` and ``no_hardware/repository``. Reading through these will give you a general idea of what ARTIQ Python is capable of and how to use it.

Functions and decorators
^^^^^^^^^^^^^^^^^^^^^^^^^

The ARTIQ compiler recognizes several specialized decorators, which determine the way the decorated function will be compiled and handled.

``@kernel`` (see :meth:`~artiq.language.core.kernel`) designates kernel functions, which will be compiled for and executed on the core device; the basic setup and background for kernels is detailed on the :doc:`getting_started_core` page. ``@subkernel`` (:meth:`~artiq.language.core.subkernel`) designates subkernel functions, which are largely similar to kernels except that they are executed on satellite devices in a DRTIO setting, with some associated limitations; they are described in more detail on the :doc:`using_drtio_subkernels` page.

``@rpc`` (:meth:`~artiq.language.core.rpc`) designates functions to be executed on the host machine, which are compiled and run in regular Python, outside of the core device's real-time limitations. Notably, functions without decorators are assumed to be host-bound by default, and treated identically to an explicitly marked ``@rpc``. As a result, the explicit decorator is only really necessary when specifying additional flags (for example, ``flags={"async"}``, see below).

``@portable`` (:meth:`~artiq.language.core.portable`) designates functions to be executed *on the same device they are called.* In other words, when called from a kernel, a portable is executed as a kernel; when called from a subkernel, it is executed as a kernel, on the same satellite device as the calling subkernel; when called from a host function, it is executed on the host machine.

``@host_only`` (:meth:`~artiq.language.core.host_only`) functions are executed fully on the host, similarly to ``@rpc``, but calling them from a kernel as an RPC will be refused by the compiler. It can be used to mark functions which should only ever be called by the host.

.. warning::
    ARTIQ goes to some lengths to cache code used in experiments correctly, so that experiments run according to the state of the code when they were started, even if the source is changed during the run time. Python itself annoyingly fails to implement this (see also `issue #416 <https://github.com/m-labs/artiq/issues/416>`_), necessitating a workaround on ARTIQ's part. One particular downstream limitation is that the ARTIQ compiler is unable to recognize decorators with path prefixes, i.e.: ::

         import artiq.experiment as aq

         [...]

            @aq.kernel
            def run(self):
                pass

    will fail to compile. As long as ``from artiq.experiment import *`` is used as in the examples, this is never an issue. If prefixes are strongly preferred, a possible workaround is to import decorators separately, as e.g. ``from artiq.language.core import kernel``.

.. _compiler-types:

ARTIQ types
^^^^^^^^^^^

Python/NumPy types correspond to ARTIQ types as follows:

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
| bytes         | TBytes                  |
+---------------+-------------------------+
| bytearray     | TByteArray              |
+---------------+-------------------------+
| list of T     | TList(T)                |
+---------------+-------------------------+
| NumPy array   | TArray(T, num_dims)     |
+---------------+-------------------------+
| range         | TRange32, TRange64      |
+---------------+-------------------------+
| numpy.int32   | TInt32                  |
+---------------+-------------------------+
| numpy.int64   | TInt64                  |
+---------------+-------------------------+
| numpy.float64 | TFloat                  |
+---------------+-------------------------+

Integers are 32-bit by default but may be converted to 64-bit with ``numpy.int64``.

The ARTIQ compiler can be thought of as overriding all built-in Python types, and types in kernel code cannot always be assumed to behave as they would in host Python. In particular, normally heap-allocated types such as arrays, lists, and strings are very limited in what they support. Strings must be constant and lists and arrays must be of constant size. Methods like ``append``, ``push``, and ``pop`` are unavailable as a matter of principle, and will not compile. Certain types, notably dictionaries, have no ARTIQ implementation and cannot be used in kernels at all.

.. tip::
    Instead of pushing or appending, preallocate for the maximum number of elements you expect with a list comprehension, i.e. ``x = [0 for _ in range(1024)]``, and then keep a variable ``n`` noting the last filled element of the array. Afterwards, ``x[0:n]`` will give you a list with that number of elements.

Multidimensional arrays are allowed (using NumPy syntax). Element-wise operations (e.g. ``+``, ``/``), matrix multiplication (``@``) and multidimensional indexing are supported; slices and views (currently) are not.

User-defined classes are supported, provided their attributes are of other supported types (attributes that are not used in the kernel are ignored and thus unrestricted). When several instances of a user-defined class are referenced from the same kernel, every attribute must have the same type in every instance of the class.

Basic ARTIQ Python
^^^^^^^^^^^^^^^^^^

Basic Python features can broadly be used inside kernels without further compunctions. This includes loops (``for`` / ``while`` / ``break`` / ``continue``), conditionals (``if`` / ``else`` / ``elif``), functions, exceptions, ``try`` / ``except`` / ``else`` blocks,  and statically typed variables of any supported types.

Kernel code can call host functions without any additional ceremony. However, such functions are assumed to return ``None``, and if a value other than ``None`` is returned, an exception is raised. To call a host function returning a value other than ``None`` its return type must be annotated, using the standard Python syntax, e.g.: ::

    def return_four() -> TInt32:
        return 4

Kernels can freely modify attributes of objects shared with the host. However, by necessity, these modifications are actually applied to local copies of the objects, as the latency of immediate writeback would be unsupportable in a real-time environment. Instead, modifications are written back *when the kernel completes;* notably, this means RPCs called by a kernel itself will only have access to the unmodified host version of the object, as the kernel hasn't finished execution yet. In some cases, accessing data on the host is better handled by calling RPCs specifically to make the desired modifications.

.. warning::

    Kernels *cannot and should not* return lists, arrays, or strings they have created, or any objects containing them; in the absence of a heap, the way these values are allocated means they cannot outlive the kernels they are created in. Trying to do so will normally be discovered by lifetime tracking and result in compilation errors, but in certain cases lifetime tracking will fail to detect a problem and experiments will encounter memory corruption at runtime. For example: ::

        def func(a):
            return a

        class ProblemReturn1(EnvExperiment):
            def build(self):
                self.setattr_device("core")

            @kernel
            def run(self):
                # results in memory corruption
                return func([1, 2, 3])

    will compile, **but corrupts at runtime.** On the other hand, lists, arrays, or strings can and should be used as inputs for RPCs, and this is the preferred method of returning data to the host. In this way the data is inherently read and sent before the kernel completes and there are no allocation issues.

Available built-in functions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

ARTIQ makes various useful built-in and mathematical functions from Python, NumPy, and SciPy available in kernel code. They are not guaranteed to be perfectly equivalent to their host namesakes (for example, ``numpy.rint()`` normally rounds-to-even, but in kernel code rounds toward zero) but their behavior should be basically predictable.


.. list-table::
    :header-rows: 1

    +   * Reference
        * Functions
    +   * `Python built-ins <https://docs.python.org/3/library/functions.html>`_
        *   - ``len()``, ``round()``, ``abs()``, ``min()``, ``max()``
            - ``print()`` (with caveats; see below)
            - all basic type conversions (``int()``, ``float()`` etc.)
    +   * `NumPy mathematic utilities <https://numpy.org/doc/stable/reference/routines.math.html>`_
        *   - ``sqrt()``, ``cbrt()``
            - ``fabs()``, ``fmax()``, ``fmin()``
            - ``floor()``, ``ceil()``, ``trunc()``, ``rint()``
    +   * `NumPy exponents and logarithms <https://numpy.org/doc/stable/reference/routines.math.html#exponents-and-logarithms>`_
        *   - ``exp()``, ``exp2()``, ``expm1()``
            - ``log()``, ``log2()``, ``log10()``
    +   * `NumPy trigonometric and hyperbolic functions <https://numpy.org/doc/stable/reference/routines.math.html#trigonometric-functions>`_
        *   - ``sin()``, ``cos()``, ``tan()``,
            - ``arcsin()``, ``arccos()``, ``arctan()``
            - ``sinh()``, ``cosh()``, ``tanh()``
            - ``arcsinh()``, ``arccosh()``, ``arctanh()``
            - ``hypot()``, ``arctan2()``
    +   * `NumPy floating point routines <https://numpy.org/doc/stable/reference/routines.math.html#floating-point-routines>`_
        *   - ``copysign()``, ``nextafter()``
    +   * `SciPy special functions <https://docs.scipy.org/doc/scipy/reference/special.html>`_
        *   - ``erf()``, ``erfc()``
            - ``gamma()``, ``gammaln()``
            - ``j0()``, ``j1()``, ``y0()``, ``y1()``

Basic NumPy array handling (``np.array()``, ``numpy.transpose()``, ``numpy.full()``, ``@``, element-wise operation, etc.) is also available. NumPy functions are implicitly broadcast when applied to arrays.

Print and logging functions
^^^^^^^^^^^^^^^^^^^^^^^^^^^

ARTIQ offers two native built-in logging functions: ``rtio_log()``, which prints to the :ref:`RTIO log <rtio-analyzer>`, as retrieved by :mod:`~artiq.frontend.artiq_coreanalyzer`, and ``core_log()``, which prints directly to the core log, regardless of context or network connection status. Both exist for debugging purposes, especially in contexts where a ``print()`` RPC is not suitable, such as in idle/startup kernels or when debugging delicate RTIO slack issues which may be significantly affected by the overhead of ``print()``.

``print()`` itself is in practice an RPC to the regular host Python ``print()``, i.e. with output either in the terminal of :mod:`~artiq.frontend.artiq_run` or in the client logs when using :mod:`~artiq.frontend.artiq_dashboard` or :mod:`~artiq.frontend.artiq_compile`. This means on one hand that it should not be used in idle, startup, or subkernels, and on the other hand that it suffers of some of the timing limitations of any other RPC, especially if the RPC queue is full. Accordingly, it is important to be aware that the timing of ``print()`` outputs can't reliably be used to debug timing in kernels, and especially not the timing of other RPCs.

.. _compiler-pitfalls:

Pitfalls
--------

Empty lists do not have valid list element types, so they cannot be used in the kernel.

Arbitrary-length integers are not supported at all on the core device; all integers are either 32-bit or 64-bit. This especially affects calculations that result in a 32-bit signed overflow. If the compiler detects a constant that can't fit into 32 bits, the entire expression will be upgraded to 64-bit arithmetic, but if all constants are small, 32-bit arithmetic is used even if the result will overflow. Overflows are not detected.

The result of calling the builtin ``round`` function is different when used with the builtin ``float`` type and the ``numpy.float64`` type on the host interpreter; ``round(1.0)`` returns an integer value 1, whereas ``round(numpy.float64(1.0))`` returns a floating point value ``numpy.float64(1.0)``. Since both ``float`` and ``numpy.float64`` are mapped to the builtin ``float`` type on the core device, this can lead to problems in functions marked ``@portable``; the workaround is to explicitly cast the argument of ``round`` to ``float``: ``round(float(numpy.float64(1.0)))`` returns an integer on the core device as well as on the host interpreter.

Flags and optimizations
-----------------------

The ARTIQ compiler runs many optimizations, most of which perform well on code that has pristine Python semantics. It also contains more powerful, and more invasive, optimizations that require opt-in to activate.

Asynchronous RPCs
^^^^^^^^^^^^^^^^^

If an RPC returns no value, it can be invoked in a way that does not block until the RPC finishes execution, but only until it is queued. (Submitting asynchronous RPCs too rapidly, as well as submitting asynchronous RPCs with arguments that are too large, can still block until completion.)

To define an asynchronous RPC, use the ``@rpc`` annotation with a flag: ::

    @rpc(flags={"async"})
    def record_result(x):
        self.results.append(x)

Fast-math flags
^^^^^^^^^^^^^^^

The compiler does not normally perform algebraically equivalent transformations on floating-point expressions, because this can dramatically change the result. However, it can be instructed to do so if all of the following are true:

* Arguments and results will not be Not-a-Number or infinite;
* The sign of a zero value is insignificant;
* Any algebraically equivalent transformations, such as reassociation or replacing division with multiplication by reciprocal, are legal to perform.

If this is the case for a given kernel, a ``fast-math`` flag can be specified to enable more aggressive optimization for this specific kernel: ::

    @kernel(flags={"fast-math"})
    def calculate(x, y, z):
        return x * z + y * z

This flag particularly benefits loops with I/O delays performed in fractional seconds rather than machine units, as well as updates to DDS phase and frequency.

Kernel invariants
^^^^^^^^^^^^^^^^^

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

In the synthetic example above, the compiler will be able to detect that the result of evaluating ``self.interval / 5.0`` never changes, even though it neither knows the value of ``self.worker.interval`` beforehand nor can see through the ``self.worker.work()`` function call, and thus can hoist the expensive floating-point division out of the loop, transforming the code for ``loop`` into an equivalent of the following: ::

        @kernel
        def loop(self):
            precomputed_delay_mu = self.core.seconds_to_mu(self.worker.interval / 5.0)
            for _ in range(100):
                delay_mu(precomputed_delay_mu)
                self.worker.work()
