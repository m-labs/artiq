Getting started
===============

.. _connecting-to-the-core-device:

Connecting to the core device
-----------------------------

As a very first step, we will turn on a LED on the core device. Create a file ``led.py`` containing the following: ::

    from artiq import *


    class LED(EnvExperiment):
        def build(self):
            self.attr_device("core")
            self.attr_device("led")

        @kernel
        def run(self):
            self.led.on()


The central part of our code is our ``LED`` class, that derives from :class:`artiq.language.environment.EnvExperiment`. Among other features, ``EnvExperiment`` calls our ``build`` method and provides the ``attr_device`` method that interfaces to the device database to create the appropriate device drivers and make those drivers accessible as ``self.core`` and ``self.led``. The ``@kernel`` decorator tells the system that the ``run`` method must be executed on the core device (instead of the host). The decorator uses ``self.core`` internally, which is why we request the core device using ``attr_device`` like any other.

Copy the files ``ddb.pyon`` and ``pdb.pyon`` (containing the device and parameter databases) from the ``examples`` folder of ARTIQ into the same directory as ``led.py`` (alternatively, you can use the ``-d`` and ``-p`` options of ``artiq_run.py``). You can open the database files using a text editor - their contents are in a human-readable format.

Run your code using ``artiq_run``, which is part of the ARTIQ front-end tools: ::

    $ artiq_run led.py

The LED of the device should turn on. Congratulations! You have a basic ARTIQ system up and running.

Host/core device interaction
----------------------------

A method or function running on the core device (which we call a "kernel") may communicate with the host by calling non-kernel functions that may accept parameters and may return a value. The "remote procedure call" (RPC) mechanisms handle automatically the communication between the host and the device of which function to call, with which parameters, and what the returned value is.

Modify the code as follows: ::

    def input_led_state():
        return int(input("Enter desired LED state: "))

    class LED(EnvExperiment):
        def build(self):
            self.attr_device("core")
            self.attr_device("led")

        @kernel
        def run(self):
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

The ``break_realtime`` call is necessary to waive the real-time requirements of the LED state change (as the ``input_led_state`` function can take an arbitrarily long time). This will become clearer later as we explain timing control.

Algorithmic features
--------------------

A number of Python algorithmic features can be used inside a kernel for compilation and execution on the core device. They include ``for`` and ``while`` loops, conditionals (``if``, ``else``, ``elif``), functions, exceptions (without parameter), and statically typed variables of the following types:

* Booleans
* 32-bit signed integers (default size)
* 64-bit signed integers (:class:`artiq.language.core.int64`)
* Signed rational numbers with 64-bit numerator and 64-bit denominator
* Double-precision floating point numbers
* Lists of the above types. Lists of lists are not supported.

For a demonstration of some of these features, see the ``mandelbrot.py`` example.

Real-time I/O
-------------

The point of running code on the core device is the ability to meet demanding real-time constraints. In particular, the core device can respond to an incoming stimulus or the result of a measurement with a low and predictable latency. We will see how to use inputs later; first, we must familiarize ourselves with how time is managed in kernels.

Create a new file ``rtio.py`` containing the following: ::

    from artiq import *

    class Tutorial(EnvExperiment):
        def build(self):
            self.attr_device("core")
            self.attr_device("ttl0")

        @kernel
        def run(self):
            for i in range(1000000):
                self.ttl0.pulse(2*us)
                delay(2*us)


Connect an oscilloscope or logic analyzer to TTL0 (pin C11 on the Pipistrello) and run ``artiq_run.py led.py``. Notice that the generated signal's period is precisely 4 microseconds, and that it has a duty cycle of precisely 50%. This is not what you would expect if the delay and the pulse were implemented with CPU-controlled GPIO: overhead from the loop management, function calls, etc. would increase the signal's period, and asymmetry in the overhead would cause duty cycle distortion.

Instead, inside the core device, output timing is generated by the gateware and the CPU only programs switching commands with certain timestamps that the CPU computes. This guarantees precise timing as long as the CPU can keep generating timestamps that are increasing fast enough. In case it fails to do that (and attempts to program an event with a timestamp in the past), the :class:`artiq.coredevice.runtime_exceptions.RTIOUnderflow` exception is raised. The kernel causing it may catch it (using a regular ``try... except...`` construct), or it will be propagated to the host.

Try reducing the period of the generated waveform until the CPU cannot keep up with the generation of switching events and the underflow exception is raised. Then try catching it: ::

    from artiq.coredevice.runtime_exceptions import RTIOUnderflow

    def print_underflow():
        print("RTIO underflow occured")

    class Tutorial(EnvExperiment):
        def build(self):
            self.attr_device("core")
            self.attr_device("ttl0")

        @kernel
        def run(self):
            try:
                for i in range(1000000):
                    self.ttl0.pulse(...)
                    delay(...)
            except RTIOUnderflow:
                print_underflow()

Parallel and sequential blocks
------------------------------

It is often necessary that several pulses overlap one another. This can be expressed through the use of ``with parallel`` constructs, in which all statements execute at the same time. The execution time of the ``parallel`` block is the execution time of its longest statement.

Try the following code and observe the generated pulses on a 2-channel oscilloscope or logic analyzer: ::

    for i in range(1000000):
        with parallel:
            self.ttl0.pulse(2*us)
            self.ttl1.pulse(4*us)
        delay(4*us)

TTL1 is assigned to the pin C10 of the Pipistrello. The name of the attributes (``ttl0`` and ``ttl1``) is used to look up hardware in the device database.

Within a parallel block, some statements can be made sequential again using a ``with sequential`` construct. Observe the pulses generated by this code: ::

    for i in range(1000000):
        with parallel:
            with sequential:
                self.ttl0.pulse(2*us)
                delay(1*us)
                self.ttl0.pulse(1*us)
            self.ttl1.pulse(4*us)
        delay(4*us)

.. warning::
    In its current implementation, ARTIQ only supports those pulse sequences that can be interleaved at compile time into a sequential series of on/off events. Combinations of ``parallel``/``sequential`` blocks that require multithreading (due to the parallel execution of long loops, complex algorithms, or algorithms that depend on external input) will cause the compiler to return an error.
