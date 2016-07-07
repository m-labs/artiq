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

The central part of our code is our ``LED`` class, that derives from :class:`artiq.language.environment.EnvExperiment`. Among other features, ``EnvExperiment`` calls our ``build`` method and provides the ``setattr_device`` method that interfaces to the device database to create the appropriate device drivers and make those drivers accessible as ``self.core`` and ``self.led``. The ``@kernel`` decorator tells the system that the ``run`` method must be executed on the core device (instead of the host). The decorator uses ``self.core`` internally, which is why we request the core device using ``setattr_device`` like any other.

Copy the file ``device_db.pyon`` (containing the device database) from the ``examples/master`` folder of ARTIQ into the same directory as ``led.py`` (alternatively, you can use the ``--device-db`` option of ``artiq_run``). You can open PYON database files using a text editor - their contents are in a human-readable format. You will probably want to set the IP address of the core device in ``device_db.pyon`` so that the computer can connect to it (it is the ``host`` parameter of the ``comm`` entry). See :ref:`device-db` for more information. The example device database is designed for the NIST QC1 hardware on the KC705; see :ref:`board-ports` for RTIO channel assignments if you need to adapt the device database to a different hardware platform.

.. note::
    If the ``led`` device is a bidirectional TTL (i.e. ``TTLInOut`` instead of ``TTLOut``), you need to put it in output (driving) mode. Add the following at the beginning of ``run``: ::

        self.led.output()
        delay(0.1*us)

.. note::
    To obtain the examples, you can find where the ARTIQ package is installed on your machine with: ::

        python3.5 -c "import artiq; print(artiq.__path__[0])"

Run your code using ``artiq_run``, which is part of the ARTIQ front-end tools: ::

    $ artiq_run led.py

The process should terminate quietly and the LED of the device should turn on. Congratulations! You have a basic ARTIQ system up and running.

Host/core device interaction
----------------------------

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

What happens is the ARTIQ compiler notices that the ``input_led_state`` function does not have a ``@kernel`` decorator and thus must be executed on the host. When the core device calls it, it sends a request to the host to execute it. The host displays the prompt, collects user input, and sends the result back to the core device, which sets the LED state accordingly.

RPC functions must always return a value of the same type. When they return a non-``None`` value, the compiler should be informed in advance of the type of the value, which is what the ``-> TBool`` annotation is for.

The ``break_realtime`` call is necessary to waive the real-time requirements of the LED state change (as the ``input_led_state`` function can take an arbitrarily long time). This will become clearer later as we explain timing control.

Real-time I/O
-------------

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
            for i in range(1000000):
                self.ttl0.pulse(2*us)
                delay(2*us)


.. note::
    If ``ttl0`` is a bidirectional channel (``TTLInOut``), it is in input (non-driving) mode by default. You need to call ``self.ttl0.output()`` as explained above for the LED.


Connect an oscilloscope or logic analyzer to TTL0 and run ``artiq_run.py led.py``. Notice that the generated signal's period is precisely 4 microseconds, and that it has a duty cycle of precisely 50%. This is not what you would expect if the delay and the pulse were implemented with CPU-controlled GPIO: overhead from the loop management, function calls, etc. would increase the signal's period, and asymmetry in the overhead would cause duty cycle distortion.

Instead, inside the core device, output timing is generated by the gateware and the CPU only programs switching commands with certain timestamps that the CPU computes. This guarantees precise timing as long as the CPU can keep generating timestamps that are increasing fast enough. In case it fails to do that (and attempts to program an event with a timestamp in the past), the :class:`artiq.coredevice.exceptions.RTIOUnderflow` exception is raised. The kernel causing it may catch it (using a regular ``try... except...`` construct), or it will be propagated to the host.

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

Parallel and sequential blocks
------------------------------

It is often necessary that several pulses overlap one another. This can be expressed through the use of ``with parallel`` constructs, in which all statements execute at the same time. The execution time of the ``parallel`` block is the execution time of its longest statement.

Try the following code and observe the generated pulses on a 2-channel oscilloscope or logic analyzer: ::

    for i in range(1000000):
        with parallel:
            self.ttl0.pulse(2*us)
            self.ttl1.pulse(4*us)
        delay(4*us)

Within a parallel block, some statements can be made sequential again using a ``with sequential`` construct. Observe the pulses generated by this code: ::

    for i in range(1000000):
        with parallel:
            with sequential:
                self.ttl0.pulse(2*us)
                delay(1*us)
                self.ttl0.pulse(1*us)
            self.ttl1.pulse(4*us)
        delay(4*us)

.. note::
    Branches of a ``parallel`` block are executed one after another, with a reset of the internal RTIO time variable before moving to the next branch. If a branch takes a lot of CPU time, it may cause an underflow when the next branch begins its execution.
