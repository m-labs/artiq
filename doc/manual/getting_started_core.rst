Getting started with the core language
======================================

.. _connecting-to-the-core-device:

Connecting to the core device
-----------------------------

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

The central part of our code is our ``LED`` class, which derives from :class:`artiq.language.environment.EnvExperiment`. Among other features, :class:`~artiq.language.environment.EnvExperiment` calls our :meth:`~artiq.language.environment.Experiment.build` method and provides the :meth:`~artiq.language.environment.HasEnvironment.setattr_device` method that interfaces to the device database to create the appropriate device drivers and make those drivers accessible as ``self.core`` and ``self.led``. The :func:`~artiq.language.core.kernel` decorator (``@kernel``) tells the system that the :meth:`~artiq.language.environment.Experiment.run` method must be compiled for and executed on the core device (instead of being interpreted and executed as regular Python code on the host). The decorator uses ``self.core`` internally, which is why we request the core device using :meth:`~artiq.language.environment.HasEnvironment.setattr_device` like any other.

Copy the file ``device_db.py`` (containing the device database) from the ``examples/master`` folder of ARTIQ into the same directory as ``led.py`` (alternatively, you can use the ``--device-db`` option of ``artiq_run``). You will probably want to set the IP address of the core device in ``device_db.py`` so that the computer can connect to it (it is the ``host`` parameter of the ``comm`` entry). See :ref:`device-db` for more information. The example device database is designed for the ``nist_clock`` hardware adapter on the KC705; see :ref:`board-ports` for RTIO channel assignments if you need to adapt the device database to a different hardware platform.

.. note::
    To obtain the examples, you can find where the ARTIQ package is installed on your machine with: ::

        python3 -c "import artiq; print(artiq.__path__[0])"

Run your code using ``artiq_run``, which is part of the ARTIQ front-end tools: ::

    $ artiq_run led.py

The process should terminate quietly and the LED of the device should turn on. Congratulations! You have a basic ARTIQ system up and running.

Host/core device interaction (RPC)
----------------------------------

A method or function running on the core device (which we call a "kernel") may communicate with the host by calling non-kernel functions that may accept parameters and may return a value. The "remote procedure call" (RPC) mechanisms handle automatically the communication between the host and the device of which function to call, with which parameters, and what the returned value is.

Modify the code as follows: ::

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

What happens is the ARTIQ compiler notices that the :meth:`input_led_state` function does not have a ``@kernel`` decorator (:func:`~artiq.language.core.kernel`) and thus must be executed on the host. When the core device calls it, it sends a request to the host to execute it. The host displays the prompt, collects user input, and sends the result back to the core device, which sets the LED state accordingly.

RPC functions must always return a value of the same type. When they return a value that is not ``None``, the compiler should be informed in advance of the type of the value, which is what the ``-> TBool`` annotation is for.

Without the :meth:`~artiq.coredevice.core.Core.break_realtime` call, the RTIO events emitted by :func:`self.led.on()` or :func:`self.led.off()` would be scheduled at a fixed and very short delay after entering :meth:`~artiq.language.environment.Experiment.run()`.
These events would fail because the RPC to :meth:`input_led_state()` can take an arbitrary amount of time and therefore the deadline for submission of RTIO events would have long passed when :func:`self.led.on()` or :func:`self.led.off()` are called.
The :meth:`~artiq.coredevice.core.Core.break_realtime` call is necessary to waive the real-time requirements of the LED state change.
It advances the timeline far enough to ensure that events can meet the submission deadline.


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

In its :meth:`~artiq.language.environment.Experiment.build` method, the experiment obtains the core device and a TTL device called ``ttl0`` as defined in the device database.
In ARTIQ, TTL is used roughly synonymous with "a single generic digital signal" and does not refer to a specific signaling standard or voltage/current levels.

When :meth:`~artiq.language.environment.Experiment.run`, the experiment first ensures that ``ttl0`` is in output mode and actively driving the device it is connected to.
Bidirectional TTL channels (i.e. :class:`~artiq.coredevice.ttl.TTLInOut`) are in input (high impedance) mode by default, output-only TTL channels (:class:`~artiq.coredevice.ttl.TTLOut`) are always in output mode.
There are no input-only TTL channels.

The experiment then drives one million 2 µs long pulses separated by 2 µs each.
Connect an oscilloscope or logic analyzer to TTL0 and run ``artiq_run.py rtio.py``.
Notice that the generated signal's period is precisely 4 µs, and that it has a duty cycle of precisely 50%.
This is not what you would expect if the delay and the pulse were implemented with register-based general purpose input output (GPIO) that is CPU-controlled.
The signal's period would depend on CPU speed, and overhead from the loop, memory management, function calls, etc, all of which are hard to predict and variable.
Any asymmetry in the overhead would manifest itself in a distorted and variable duty cycle.

Instead, inside the core device, output timing is generated by the gateware and the CPU only programs switching commands with certain timestamps that the CPU computes.

This guarantees precise timing as long as the CPU can keep generating timestamps that are increasing fast enough. In case it fails to do that (and attempts to program an event with a timestamp smaller than the current RTIO clock timestamp), a :exc:`~artiq.coredevice.exceptions.RTIOUnderflow` exception is raised. The kernel causing it may catch it (using a regular ``try... except...`` construct), or it will be propagated to the host.

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

It is often necessary that several pulses overlap one another. This can be expressed through the use of ``with parallel`` constructs, in which the events generated by the individual statements are executed at the same time. The duration of the ``parallel`` block is the duration of its longest statement.

Try the following code and observe the generated pulses on a 2-channel oscilloscope or logic analyzer: ::

    for i in range(1000000):
        with parallel:
            self.ttl0.pulse(2*us)
            self.ttl1.pulse(4*us)
        delay(4*us)

ARTIQ can implement ``with parallel`` blocks without having to resort to any of the typical parallel processing approaches.
It simply remembers the position on the timeline when entering the ``parallel`` block and then seeks back to that position after submitting the events generated by each statement.
In other words, the statements in the ``parallel`` block are actually executed sequentially, only the RTIO events generated by them are scheduled to be executed in parallel.
Note that if a statement takes a lot of CPU time to execute (this different from the events scheduled by a statement taking a long time), it may cause a subsequent statement to miss the deadline for timely submission of its events.
This then causes a :exc:`~artiq.coredevice.exceptions.RTIOUnderflow` exception to be raised.

Within a parallel block, some statements can be made sequential again using a ``with sequential`` construct. Observe the pulses generated by this code: ::

    for i in range(1000000):
        with parallel:
            with sequential:
                self.ttl0.pulse(2*us)
                delay(1*us)
                self.ttl0.pulse(1*us)
            self.ttl1.pulse(4*us)
        delay(4*us)

Particular care needs to be taken when working with ``parallel`` blocks in cases where a large number of RTIO events are generated as it possible to create sequencing errors (`RTIO sequence error`). Sequence errors do not halt execution of the kernel for performance reasons and instead are reported in the core log. If the ``aqctl_corelog`` process has been started with ``artiq_ctlmgr``, then these errors will be posted to the master log. However, if an experiment is executed through ``artiq_run``, these errors will not be visible outside of the core log.

A sequence error is caused when the scalable event dispatcher (SED) cannot queue an RTIO event due to its timestamp being the same as or earlier than another event in its queue. By default, the SED has 8 lanes which allows ``parallel`` events to work without sequence errors in most cases, however if many (>8) events are queued with conflicting timestamps this error can surface.

These errors can usually be overcome by reordering the generation of the events. Alternatively, the number of SED lanes can be increased in the gateware.

.. _rtio-analyzer-example:

RTIO analyzer
-------------

The core device records the real-time I/O waveforms into a circular buffer. It is possible to dump any Python object so that it appears alongside the waveforms using the ``rtio_log`` function, which accepts a channel name (i.e. a log target) as the first argument: ::

    from artiq.experiment import *


    class Tutorial(EnvExperiment):
        def build(self):
            self.setattr_device("core")
            self.setattr_device("ttl0")

        @kernel
        def run(self):
            self.core.reset()
            for i in range(100):
                self.ttl0.pulse(...)
                rtio_log("ttl0", "i", i)
                delay(...)

Afterwards, the recorded data can be extracted and written to a VCD file using ``artiq_coreanalyzer -w rtio.vcd`` (see: :ref:`core-device-rtio-analyzer-tool`). VCD files can be viewed using third-party tools such as GtkWave.


Direct Memory Access (DMA)
--------------------------

DMA allows you to store fixed sequences of pulses in system memory, and have the DMA core in the FPGA play them back at high speed. Pulse sequences that are too fast for the CPU (i.e. would cause RTIO underflows) can still be generated using DMA. The only modification of the sequence that the DMA core supports is shifting it in time (so it can be played back at any position of the timeline), everything else is fixed at the time of recording the sequence.

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
                # all RTIO operations now go to the "pulses"
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
