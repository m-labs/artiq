Getting started with the core device
====================================

As a very first step, we will turn on a LED on the core device. Create a file ``led.py`` containing the following: ::

    from artiq.experiment import *


    class LED(EnvExperiment):
        def build(self):
            self.setattr_device("core")
            self.setattr_device("led")

        @kernel
        def run(self):
            self.core.reset()
            self.led.on()

The central part of our code is our ``LED`` class, which derives from :class:`~artiq.language.environment.EnvExperiment`. Almost all experiments should derive from this class, which provides access to the environment as well as including the necessary experiment framework from the base-level :class:`~artiq.language.environment.Experiment`. It will call our :meth:`~artiq.language.environment.HasEnvironment.build` at the right time and provides the :meth:`~artiq.language.environment.HasEnvironment.setattr_device` we use to gain access to our devices ``core`` and ``led``. The :func:`~artiq.language.core.kernel` decorator (``@kernel``) tells the system that the :meth:`~artiq.language.environment.Experiment.run` method is a kernel and must be compiled for and executed on the core device (instead of being interpreted and executed as regular Python code on the host).

Before you can run the example experiment, you will need to supply ARTIQ with the device database for your system, just as you did when configuring the core device. Make sure ``device_db.py`` is in the same directory as ``led.py``. Check once again that the field ``core_addr``, placed at the top of the file, matches the current IP address of your core device.

If you don't have a ``device_db.py`` for your system, consult :ref:`device-db` to find out how to construct one. You can also find example device databases in the ``examples`` folder of ARTIQ, sorted into corresponding subfolders by core device, which you can edit to match your system.

.. note::
    To access the examples, find where the ARTIQ package is installed on your machine with: ::

        python3 -c "import artiq; print(artiq.__path__[0])"

Run your code using :mod:`~artiq.frontend.artiq_run`, which is one of the ARTIQ front-end tools: ::

    $ artiq_run led.py

The process should terminate quietly and the LED of the device should turn on. Congratulations! You have a basic ARTIQ system up and running.

Host/core device interaction (RPC)
----------------------------------

A method or function running on the core device (which we call a "kernel") may communicate with the host by calling non-kernel functions that may accept parameters and may return a value. The "remote procedure call" (RPC) mechanisms automatically handle the communication between the host and the device, conveying between them what function to call, what parameters to call it with, and the resulting value, once returned.

Modify ``led.py`` as follows: ::

    def input_led_state() -> TBool:
        return input("Enter desired LED state: ") == "1"

    class LED(EnvExperiment):
        def build(self):
            self.setattr_device("core")
            self.setattr_device("led")

        @kernel
        def run(self):
            self.core.reset()
            s = input_led_state()
            self.core.break_realtime()
            if s:
                self.led.on()
            else:
                self.led.off()


You can then turn the LED off and on by entering 0 or 1 at the prompt that appears: ::

    $ artiq_run led.py
    Enter desired LED state: 1
    $ artiq_run led.py
    Enter desired LED state: 0

What happens is that the ARTIQ compiler notices that the ``input_led_state`` function does not have a ``@kernel`` decorator (:func:`~artiq.language.core.kernel`) and thus must be executed on the host. When the function is called on the core device, it sends a request to the host, which executes it. The core device waits until the host returns, and then continues the kernel; in this case, the host displays the prompt, collects user input, and the core device sets the LED state accordingly.

The return type of all RPC functions must be known in advance. If the return value is not ``None``, the compiler requires a type annotation, like ``-> TBool`` in the example above. See also :ref:`compiler-types`.

Without the :meth:`~artiq.coredevice.core.Core.break_realtime` call, the RTIO events emitted by :meth:`self.led.on() <artiq.coredevice.ttl.TTLInOut.on>` or :meth:`self.led.off() <artiq.coredevice.ttl.TTLInOut.off>` would be scheduled at a fixed and very short delay after entering :meth:`~artiq.language.environment.Experiment.run()`. These events would fail because the RPC to ``input_led_state()`` can take an arbitrarily long amount of time, and therefore the deadline for the submission of RTIO events would have long passed when :meth:`self.led.on() <artiq.coredevice.ttl.TTLInOut.on>` or :meth:`self.led.off() <artiq.coredevice.ttl.TTLInOut.off>` are called (that is, the ``rtio_counter_mu`` wall clock will have advanced far ahead of the timeline cursor ``now_mu``, and an :exc:`~artiq.coredevice.exceptions.RTIOUnderflow` would result; see :doc:`rtio` for the full explanation of wall clock vs. timeline.) The :meth:`~artiq.coredevice.core.Core.break_realtime` call is necessary to waive the real-time requirements of the LED state change. Rather than delaying by any particular time interval, it reads ``rtio_counter_mu`` and moves up the ``now_mu`` cursor far enough to ensure it's once again safely ahead of the wall clock.

Real-time Input/Output (RTIO)
-----------------------------

The point of running code on the core device is the ability to meet demanding real-time constraints. In particular, the core device can respond to an incoming stimulus or the result of a measurement with a low and predictable latency. We will see how to use inputs later; first, we must familiarize ourselves with how time is managed in kernels.

Create a new file ``rtio.py`` containing the following: ::

    from artiq.experiment import *


    class Tutorial(EnvExperiment):
        def build(self):
            self.setattr_device("core")
            self.setattr_device("ttl0")

        @kernel
        def run(self):
            self.core.reset()
            self.ttl0.output()
            for i in range(1000000):
                delay(2*us)
                self.ttl0.pulse(2*us)

In its :meth:`~artiq.language.environment.HasEnvironment.build` method, the experiment obtains the core device and a TTL device called ``ttl0`` as defined in the device database. In ARTIQ, TTL is used roughly synonymous with "a single generic digital signal" and does not refer to a specific signaling standard or voltage/current levels.

When :meth:`~artiq.language.environment.Experiment.run`, the experiment first ensures that ``ttl0`` is in output mode and actively driving the device it is connected to.Bidirectional TTL channels (i.e. :class:`~artiq.coredevice.ttl.TTLInOut`) are in input (high impedance) mode by default, output-only TTL channels (:class:`~artiq.coredevice.ttl.TTLOut`) are always in output mode. There are no input-only TTL channels.

The experiment then drives one million 2 µs long pulses separated by 2 µs each. Connect an oscilloscope or logic analyzer to TTL0 and run ``artiq_run rtio.py``. Notice that the generated signal's period is precisely 4 µs, and that it has a duty cycle of precisely 50%. This is not what one would expect if the delay and the pulse were implemented with register-based general purpose input output (GPIO) that is CPU-controlled. The signal's period would depend on CPU speed, and overhead from the loop, memory management, function calls, etc., all of which are hard to predict and variable. Any asymmetry in the overhead would manifest itself in a distorted and variable duty cycle.

Instead, inside the core device, output timing is generated by the gateware and the CPU only programs switching commands with certain timestamps that the CPU computes.

This guarantees precise timing as long as the CPU can keep generating timestamps that are increasing fast enough. In the case that it fails to do so (and attempts to program an event with a timestamp smaller than the current RTIO clock timestamp), :exc:`~artiq.coredevice.exceptions.RTIOUnderflow` is raised. The kernel causing it may catch it (using a regular ``try... except...`` construct), or allow it to propagate to the host.

Try reducing the period of the generated waveform until the CPU cannot keep up with the generation of switching events and the underflow exception is raised. Then try catching it: ::

    from artiq.experiment import *


    def print_underflow():
        print("RTIO underflow occured")

    class Tutorial(EnvExperiment):
        def build(self):
            self.setattr_device("core")
            self.setattr_device("ttl0")

        @kernel
        def run(self):
            self.core.reset()
            try:
                for i in range(1000000):
                    self.ttl0.pulse(...)
                    delay(...)
            except RTIOUnderflow:
                print_underflow()


Parallel and sequential blocks
------------------------------

It is often necessary for several pulses to overlap one another. This can be expressed through the use of the ``with parallel`` construct, in which the events generated by individual statements are scheduled to execute at the same time, rather than sequentially. The duration of the ``parallel`` block is the duration of its longest statement.

Try the following code and observe the generated pulses on a 2-channel oscilloscope or logic analyzer: ::

    from artiq.experiment import *

    class Tutorial(EnvExperiment):
        def build(self):
            self.setattr_device("core")
            self.setattr_device("ttl0")
            self.setattr_device("ttl1")

        @kernel
        def run(self):
            self.core.reset()
            for i in range(1000000):
                with parallel:
                    self.ttl0.pulse(2*us)
                    self.ttl1.pulse(4*us)
                delay(4*us)

ARTIQ can implement ``with parallel`` blocks without having to resort to any of the typical parallel processing approaches. It simply remembers its position on the timeline (``now_mu``) when entering the ``parallel`` block and resets to that position after each individual statement. At the end of the block, the cursor is advanced to the furthest position it reached during the block. In other words, the statements in a ``parallel`` block are actually executed sequentially. Only the RTIO events generated by the statements are *scheduled* in parallel.

Remember that while ``now_mu`` resets at the beginning of each statement in a ``parallel`` block, the wall clock advances regardless. If a particular statement takes a long time to execute (which is different from -- and unrelated to! -- the events *scheduled* by the statement taking a long time), the wall clock may advance past the reset value, putting any subsequent statements inside the block into a situation of negative slack (i.e., resulting in :exc:`~artiq.coredevice.exceptions.RTIOUnderflow` ). Sometimes underflows may be avoided simply by reordering statements within the parallel block. This especially applies to input methods, which generally necessarily block CPU progress until the wall clock has caught up to or overtaken the cursor.

Within a parallel block, some statements can be scheduled sequentially again using a ``with sequential`` block. Observe the pulses generated by this code: ::

    for i in range(1000000):
        with parallel:
            with sequential:
                self.ttl0.pulse(2*us)
                delay(1*us)
                self.ttl0.pulse(1*us)
            self.ttl1.pulse(4*us)
        delay(4*us)

.. warning::
    ``with parallel`` specifically 'parallelizes' the *top-level* statements inside a block. Consider as an example: ::

            for i in range(1000000):
                with parallel:
                    self.ttl0.pulse(2*us)       # 1
                    if True:                    # 2
                        self.ttl1.pulse(2*us)   # 3
                        self.ttl2.pulse(2*us)   # 4
                delay(4*us)

    This code will not schedule the three pulses to ``ttl0``, ``ttl1``, and ``ttl2`` in parallel. Rather, the pulse to ``ttl1`` is 'parallelized' *with the if statement*. The timeline cursor resets once, at the beginning of statement #2; it will not repeat the reset at the deeper indentation level for #3 or #4.

    In practice, the pulses to ``ttl0`` and ``ttl1`` will execute simultaneously, and the pulse to ``ttl2`` will execute after the pulse to ``ttl1``, bringing the total duration of the ``parallel`` block to 4 us. Internally, statements #3 and #4, contained within the top-level if statement, are considered an atomic sequence and executed within an implicit ``with sequential``. To execute #3 and #4 in parallel, it is necessary to place them inside a second, nested ``parallel`` block within the if statement.

Particular care needs to be taken when working with ``parallel`` blocks which generate large numbers of RTIO events, as it is possible to cause sequencing issues in the gateware; see also :ref:`sequence-errors`.

.. _rtio-analyzer:

RTIO analyzer
-------------

The core device records all real-time I/O waveforms, as well as the variation of RTIO slack, into a circular buffer, the contents of which can be extracted using :mod:`~artiq.frontend.artiq_coreanalyzer`. Try for example: ::

    from artiq.experiment import *

    class Tutorial(EnvExperiment):
        def build(self):
            self.setattr_device("core")
            self.setattr_device("ttl0")

        @kernel
        def run(self):
            self.core.reset()
            for i in range(5):
                self.ttl0.pulse(0.1 * ms)
                delay(0.1 * ms)

When using :mod:`~artiq.frontend.artiq_run`, the recorded buffer data can be extracted directly into the terminal, using a command in the form of: ::

    $ artiq_coreanalyzer -p

.. note::
    The first time this command is run, it will retrieve the entire contents of the analyzer buffer, which may include every experiment you have run so far. For a more manageable introduction, run the analyzer once to clear the buffer, run the experiment, and then run the analyzer a second time, so that only the data from this single experiment is displayed.

This will produce a list of the exact output events submitted to RTIO, printed in chronological order, along with the state of both ``now_mu`` and ``rtio_counter_mu``. While useful in diagnosing some specific gateware errors (in particular, :ref:`sequencing issues <sequence-errors>`), it isn't the most readable of formats. An alternate is to export to VCD, which can be viewed using third-party tools such as GtkWave. Run the experiment again, and use a command in the form of: ::

    $ artiq_coreanalyzer -w <file_name>.vcd

The ``<file_name>.vcd`` file should be immediately created and written. Check the directory the command was run in to find it.

.. tip::

    To view e.g. RTIO slack in GtkWave, drag the ``rtio_slack`` signal into the 'Signals' dock, under ``Time``. By default, the data will be presented in a raw form which you will probably not find particularly useful. For RTIO slack in particular, left-click, select ``Data Format > BitsToReal``, then ``Data Format > Analog``, to see a stepped waveform like that which the dashboard displays. Note also that the 'Waves' dock timescale is probably zoomed in very far; you may need to zoom out by some distance to see the effects of your experiment.

The easiest way to view recorded analyzer data, however, is directly in the ARTIQ dashboard, a feature which will be presented later in :ref:`interactivity-waveform`.

.. _getting-started-dma:

Direct Memory Access (DMA)
--------------------------

DMA allows for storing fixed sequences of RTIO events in system memory and having the DMA core in the FPGA play them back at high speed. Provided that the specifications of a desired event sequence are known far enough in advance, and no other RTIO issues (collisions, sequence errors) are provoked, even extremely fast and detailed event sequences can always be generated and executed. RTIO underflows occur when events cannot be generated *as fast as* they need to be executed, resulting in an exception when the wall clock 'catches up'. The solution is to record these sequences to the DMA core. Once recorded, event sequences are fixed and cannot be modified, but can be safely replayed very quickly at any position in the timeline, potentially repeatedly.

Try this: ::

    from artiq.experiment import *


    class DMAPulses(EnvExperiment):
        def build(self):
            self.setattr_device("core")
            self.setattr_device("core_dma")
            self.setattr_device("ttl0")

        @kernel
        def record(self):
            with self.core_dma.record("pulses"):
                # all RTIO operations now_mu go to the "pulses"
                # DMA buffer, instead of being executed immediately.
                for i in range(50):
                    self.ttl0.pulse(100*ns)
                    delay(100*ns)

        @kernel
        def run(self):
            self.core.reset()
            self.record()
            # prefetch the address of the DMA buffer
            # for faster playback trigger
            pulses_handle = self.core_dma.get_handle("pulses")
            self.core.break_realtime()
            while True:
                # execute RTIO operations in the DMA buffer
                # each playback advances the timeline by 50*(100+100) ns
                self.core_dma.playback_handle(pulses_handle)

.. note::
    Only output events are redirected to the DMA core. Input methods inside a ``with dma`` block will be called as they would be outside of the block, in the current real-time context, and input events will be buffered normally, not to DMA.

For more documentation on the methods used, see the :mod:`artiq.coredevice.dma` reference.
