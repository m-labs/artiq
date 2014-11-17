Getting started
===============

Connecting to the core device
-----------------------------

As a very first step, we will turn on a LED on the core device. Create a file ``led.py`` containing the following: ::

    from artiq import *
    from artiq.coredevice import comm_serial, core, gpio

    class LED(AutoContext):
        parameters = "led"

        @kernel
        def run(self):
            self.led.set(1)

    if __name__ == "__main__":
        with comm_serial.Comm() as comm:
            core_driver = core.Core(comm)
            led_driver = gpio.GPIOOut(core=core_driver, channel=0)
            exp = LED(core=core_driver, led=led_driver)
            exp.run()

The central part of our code is our ``LED`` class, that derives from :class:`artiq.language.core.AutoContext`. ``AutoContext`` is part of the mechanism that attaches device drivers and retrieves parameters according to a database. We are not using the database yet; instead, we import and create the device drivers and establish communication with the core device manually. The ``parameters`` string gives the list of devices (and parameters) that our class needs in order to operate. ``AutoContext`` sets them as object attributes, so our ``led`` parameter becomes accessible as ``self.led``. Finally, the ``@kernel`` decorator tells the system that the ``run`` method must be executed on the core device (instead of the host).

Run this example with: ::

    python3 led.py

The LED of the device should turn on. Congratulations! You have a basic ARTIQ system up and running.

Host/core device interaction
----------------------------

A method or function running on the core device (which we call a "kernel") may communicate with the host by calling non-kernel functions that may accept parameters and may return a value. The "remote procedure call" (RPC) mechanisms handle automatically the communication between the host and the device of which function to call, with which parameters, and what the returned value is.

Modify the code as follows: ::

    def input_led_state():
        return int(input("Enter desired LED state: "))

    class LED(AutoContext):
        parameters = "led"

        @kernel
        def run(self):
            self.led.set(input_led_state())

You can then turn the LED off and on by entering 0 or 1 at the prompt that appears: ::

    $ python3 led.py
    Enter desired LED state: 1
    $ python3 led.py
    Enter desired LED state: 0

What happens is the ARTIQ compiler notices that the ``input_led_state`` function does not have a ``@kernel`` decorator and thus must be executed on the host. When the core device calls it, it sends a request to the host to execute it. The host displays the prompt, collects user input, and sends the result back to the core device, which sets the LED state accordingly.

Algorithmic features
--------------------

A number of Python algorithmic features can be used inside a kernel for compilation and execution on the core device. They include ``for`` and ``while`` loops, conditionals (``if``, ``else``, ``elif``), functions, exceptions (without parameter), and statically typed variables of the following types:

* Booleans
* 32-bit signed integers (default size)
* 64-bit signed integers (:class:`artiq.language.core.int64`)
* Signed rational numbers with 64-bit numerator and 64-bit denominator
* Double-precision floating point numbers
* Arrays of the above types and arrays of arrays, at an arbitrary depth (:class:`artiq.language.core.array`)

For a demonstration of some of these features, see the ``mandelbrot.py`` example.

Real-time I/O
-------------

The point of running code on the core device is the ability to meet demanding real-time constraints. In particular, the core device can respond to an incoming stimulus or the result of a measurement with a low and predictable latency. We will see how to use inputs later; first, we must familiarize ourselves with how time is managed in kernels.

Create a new file ``rtio.py`` containing the following: ::

    from artiq import *
    from artiq.coredevice import comm_serial, core, rtio

    class Tutorial(AutoContext):
        parameters = "o"

        @kernel
        def run(self):
            for i in range(1000000):
                self.o.pulse(2*us)
                delay(2*us)

    if __name__ == "__main__":
        with comm_serial.Comm() as comm:
            core_driver = core.Core(comm)
            out_driver = rtio.RTIOOut(core=core_driver, channel=1)
            exp = Tutorial(core=core_driver, o=out_driver)
            exp.run()

Connect an oscilloscope or logic analyzer to the RTIO channel 1 (pin C11 on the Papilio Pro) and run ``python3 rtio.py``. Notice that the generated signal's period is precisely 4 microseconds, and that it has a duty cycle of precisely 50%. This is not what you would expect if the delay and the pulse were implemented with CPU-controlled GPIO: overhead from the loop management, function calls, etc. would increase the signal's period, and asymmetry in the overhead would cause duty cycle distortion.

Instead, inside the core device, output timing is generated by the gateware and the CPU only programs switching commands with certain timestamps that the CPU computes. This guarantees precise timing as long as the CPU can keep generating timestamps that are increasing fast enough. In case it fails to do that (and attempts to program an event with a timestamp in the past), the :class:`artiq.coredevice.runtime_exceptions.RTIOUnderflow` exception is raised. The kernel causing it may catch it (using a regular ``try... except...`` construct), or it will be propagated to the host.

Try reducing the period of the generated waveform until the CPU cannot keep up with the generation of switching events and the underflow exception is raised. Then try catching it: ::

    from artiq.coredevice.runtime_exceptions import RTIOUnderflow

    def print_underflow():
        print("RTIO underflow occured")

    class Tutorial(AutoContext):
        parameters = "led o"

        @kernel
        def run(self):
            self.led.set(0)
            try:
                for i in range(1000000):
                    self.o.pulse(...)
                    delay(...)
            except RTIOUnderflow:
                self.led.set(1)
                print_underflow()

Parallel and sequential blocks
------------------------------

It is often necessary that several pulses overlap one another. This can be expressed through the use of ``with parallel`` constructs, in which all statements execute at the same time. The execution time of the ``parallel`` block is the execution time of its longest statement.

Try the following code and observe the generated pulses on a 2-channel oscilloscope or logic analyzer: ::

    for i in range(1000000):
        with parallel:
            self.o1.pulse(2*us)
            self.o2.pulse(4*us)
        delay(4*us)

If you assign ``o2`` to the RTIO channel 2, the signal will be generated on the pin C10 of the Papilio Pro.

Within a parallel block, some statements can be made sequential again using a ``with sequential`` construct. Observe the pulses generated by this code: ::

    for i in range(1000000):
        with parallel:
            with sequential:
                self.o1.pulse(2*us)
                delay(1*us)
                self.o1.pulse(1*us)
            self.o2.pulse(4*us)
        delay(4*us)

.. warning::
    In its current implementation, ARTIQ only supports those pulse sequences that can be interleaved at compile time into a sequential series of on/off events. Combinations of ``parallel``/``sequential`` blocks that require multithreading (due to the parallel execution of long loops, complex algorithms, or algorithms that depend on external input) will cause the compiler to return an error.
