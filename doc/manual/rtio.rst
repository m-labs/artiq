ARTIQ Real-Time I/O Concepts
============================

The ARTIQ Real-Time I/O design employs several concepts to achieve its goals of high timing resolution on the nanosecond scale and low latency on the microsecond scale while still not sacrificing a readable and extensible language.

In a typical environment two very different classes of hardware need to be controlled.
One class is the vast arsenal of diverse laboratory hardware that interfaces with and is controlled from a typical PC.
The other is specialized real-time hardware
that requires tight coupling and a low-latency interface to a CPU.
The ARTIQ code that describes a given experiment is composed of two types of "programs":
regular Python code that is executed on the host and ARTIQ *kernels* that are executed on a *core device*.
The CPU that executes the ARTIQ kernels has direct access to specialized programmable I/O timing logic (part of the *gateware*).
The two types of code can invoke each other and transitions between them are seamless.

The ARTIQ kernels do not interface with the real-time gateware directly.
That would lead to imprecise, indeterminate, and generally unpredictable timing.
Instead the CPU operates at one end of a bank of FIFO (first-in-first-out) buffers while the real-time gateware at the other end guarantees the *all or nothing* level of excellent timing precision.
A FIFO for an output channel hold timestamps and event data describing when and what is to be executed.
The CPU feeds events into this FIFO.
A FIFO for an input channel contains timestamps and event data for events that have been recorded by the real-time gateware and are waiting to be read out by
the CPU on the other end.


The timeline
------------

The set of all input and output events on all channels constitutes the *timeline*.
A high resolution wall clock (``rtio_counter``) counts clock cycles and causes output events to be executed when their timestamp matches the clock and input events to be recorded and stamped with the current clock value accordingly.

The kernel runtime environment maintains a timeline cursor (called ``now``) used as the timestamp when output events are submitted to the FIFOs.
This timeline cursor can be moved forward or backward on the timeline relative to its current value using :func:`artiq.language.core.delay` and :func:`artiq.language.core.delay_mu`, the later being a delay given in *machine units* as opposed to SI units.
The absolute value of ``now`` on the timeline can be retrieved using :func:`artiq.language.core.now_mu` and it can be set using :func:`artiq.language.core.at_mu`.
RTIO timestamps, the timeline cursor, and the ``rtio_counter`` wall clock are all relative to the core device startup/boot time.
The wall clock keeps running across experiments.

Absolute timestamps can be large numbers.
They are represented internally as 64-bit integers with a resolution of typically a nanosecond and a range of hundreds of years.
Conversions between such a large integer number and a floating point representation can cause loss of precision through cancellation.
When computing the difference of absolute timestamps, use ``self.core.mu_to_seconds(t2-t1)``, not ``self.core.mu_to_seconds(t2)-self.core.mu_to_seconds(t1)`` (see :meth:`artiq.coredevice.Core.mu_to_seconds`).
When accumulating time, do it in machine units and not in SI units, so that rounding errors do not accumulate.

The following basic example shows how to place output events on the timeline.
It emits a precisely timed 2 µs pulse::

  ttl.on()
  delay(2*us)
  ttl.off()

The device ``ttl`` represents a single digital output channel
(:class:`artiq.coredevice.ttl.TTLOut`).
The :meth:`artiq.coredevice.ttl.TTLOut.on` method places an rising edge on the timeline at the current cursor position (``now``).
Then the cursor is moved forward 2 µs and a falling edge event is placed at the new cursor position.
Then later, when the wall clock reaches the respective timestamps the RTIO gateware executes the two events.

The following diagram shows what is going on at the different levels of the software and gateware stack (assuming one machine unit of time is 1 ns):

.. wavedrom::

  {
    "signal": [
      {"name": "kernel", "wave": "x32.3x", "data": ["on()", "delay(2*us)", "off()"], "node": "..A.XB"},
      {"name": "now", "wave": "2...2.", "data": ["7000", "9000"], "node": "..P..Q"},
      {},
      {"name": "slack", "wave": "x2x.2x", "data": ["4400", "5800"]},
      {},
      {"name": "rtio_counter", "wave": "x2x|2x|2x2x", "data": ["2600", "3200", "7000", "9000"], "node": "       V.W"},
      {"name": "ttl", "wave": "x1.0", "node": " R.S", "phase": -6.5},
      {                               "node": " T.U", "phase": -6.5}
    ],
    "edge": [
      "A~>R", "P~>R", "V~>R", "B~>S", "Q~>S", "W~>S",
      "R-T", "S-U", "T<->U 2µs"
    ]
  }

The sequence is exactly equivalent to::

  ttl.pulse(2*us)

The :meth:`artiq.coredevice.ttl.TTLOut.pulse` method advances the timeline cursor (using ``delay()``) while other methods such as :meth:`artiq.coredevice.ttl.TTLOut.on`, :meth:`artiq.coredevice.ttl.TTLOut.off`, :meth:`artiq.coredevice.ad9914.set`. The latter are called *zero-duration* methods.

Underflow exceptions
--------------------

An RTIO event must always be programmed with a timestamp in the future.
In other words, the timeline cursor ``now`` must be after the current wall clock ``rtio_counter``: the past can not be altered.
The following example tries to place an rising edge event on the timeline.
If the current cursor is in the past, an :class:`artiq.coredevice.exceptions.RTIOUnderflow` exception is thrown.
The experiment attempts to handle the exception by moving the cursor forward and repeating the programming of the rising edge::

  try:
      ttl.on()
  except RTIOUnderflow:
      # try again at the next mains cycle
      delay(16.6667*ms)
      ttl.on()

.. wavedrom::

  {
    "signal": [
      {"name": "kernel", "wave": "x34..2.3x", "data": ["on()", "RTIOUnderflow", "delay()", "on()"], "node": "..AB....C", "phase": -3},
      {"name": "now_mu", "wave": "2.....2", "data": ["t0", "t1"], "node": ".D.....E", "phase": -4},
      {},
      {"name": "slack", "wave": "2x....2", "data": ["< 0", "> 0"], "node": ".T", "phase": -4},
      {},
      {"name": "rtio_counter", "wave": "x2x.2x....2x2", "data": ["t0", "> t0", "< t1", "t1"], "node": "............P"},
      {"name": "tll", "wave": "x...........1", "node": ".R..........S", "phase": -0.5}
    ],
    "edge": [
      "A-~>R forbidden", "D-~>R", "T-~B exception",
      "C~>S allowed", "E~>S", "P~>S"
    ]
  }

To track down ``RTIOUnderflows`` in an experiment there are a few approaches:

  * Exception backtraces show where underflow has occurred while executing the
    code.
  * The :any:`integrated logic analyzer <core-device-rtio-analyzer-tool>` shows the timeline context that lead to the exception. The analyzer is always active and supports plotting of RTIO slack. RTIO slack is the difference between timeline cursor and wall clock time (``now - rtio_counter``).

Sequence errors
---------------
A sequence error happens when the sequence of coarse timestamps cannot be supported by the gateware. For example, there may have been too many timeline rewinds.

Internally, the gateware stores output events in an array of FIFO buffers (the "lanes") and the timestamps in each lane much be strictly increasing. The gateware selects a different lane when an event with a decreasing or equal timestamp is submitted. A sequence error occurs when no appropriate lane can be found.

Notes:

* Strictly increasing timestamps never cause sequence errors. 
* Configuring the gateware with more lanes for the RTIO core reduces the frequency of sequence errors.
* The number of lanes is a hard limit on the number of simultaneous RTIO output events.
* Whether a particular sequence of timestamps causes a sequence error or not is fully deterministic (starting from a known RTIO state, e.g. after a reset). Adding a constant offset to the whole sequence does not affect the result.

The offending event is discarded and the RTIO core keeps operating.

This error is reported asynchronously via the core device log: for performance reasons with DRTIO, the CPU does not wait for an error report from the satellite after writing an event. Therefore, it is not possible to raise an exception precisely.

Collisions
----------
A collision happens when more than one event is submitted on a given channel with the same coarse timestamp, and that channel does not implement replacement behavior or the fine timestamps are different.

Coarse timestamps correspond to the RTIO system clock (typically around 125MHz) whereas fine timestamps correspond to the RTIO SERDES clock (typically around 1GHz). Different channels may have different ratios between the coarse and fine timestamp clock frequencies.

The offending event is discarded and the RTIO core keeps operating.

This error is reported asynchronously via the core device log: for performance reasons with DRTIO, the CPU does not wait for an error report from the satellite after writing an event. Therefore, it is not possible to raise an exception precisely.

Busy errors
-----------

A busy error happens when at least one output event could not be executed because the channel was already busy executing a previous event.

The offending event was discarded.

This error is reported asynchronously via the core device log.

Input channels and events
-------------------------

Input channels detect events, timestamp them, and place them in a buffer for the experiment to read out.
The following example counts the rising edges occurring during a precisely timed 500 ns interval.
If more than 20 rising edges are received, it outputs a pulse::

  if input.count(input.gate_rising(500*ns)) > 20:
      delay(2*us)
      output.pulse(500*ns)

The :meth:`artiq.coredevice.ttl.TTLInOut.count` method of an input channel will often lead to a situation of negative slack (timeline cursor ``now`` smaller than the current wall clock ``rtio_counter``):
The :meth:`artiq.coredevice.ttl.TTLInOut.gate_rising` method leaves the timeline cursor at the closing time of the gate. ``count()`` must necessarily wait until the gate closing event has actually been executed, at which point ``rtio_counter > now``: ``count()`` synchronizes timeline cursor (``now``) and wall clock (``rtio_counter``). In these situations, a ``delay()`` is necessary to re-establish positive slack so that further output events can be placed.

Similar situations arise with methods such as :meth:`artiq.coredevice.ttl.TTLInOut.sample_get` and :meth:`artiq.coredevice.ttl.TTLInOut.watch_done`.

.. wavedrom::

  {
    "signal": [
      {"name": "kernel", "wave": "3..5.|2.3..x..", "data": ["gate_rising()", "count()", "delay()", "pulse()"], "node": ".A.B..C.ZD.E"},
      {"name": "now_mu", "wave": "2.2..|..2.2.", "node": ".P.Q....XV.W"},
      {},
      {},
      {"name": "input gate", "wave": "x1.0", "node": ".T.U", "phase": -2.5},
      {"name": "output", "wave": "x1.0", "node": ".R.S", "phase": -10.5}
    ],
    "edge": [
      "A~>T", "P~>T", "B~>U", "Q~>U", "U~>C", "D~>R", "E~>S", "V~>R", "W~>S"
    ]
  }

Overflow exceptions
-------------------

The RTIO input channels buffer input events received while an input gate is open, or at certain points in time when using the sampling API (:meth:`artiq.coredevice.ttl.TTLInOut.sample_input`).
The events are kept in a FIFO until the CPU reads them out via e.g. :meth:`artiq.coredevice.ttl.TTLInOut.count`, :meth:`artiq.coredevice.ttl.TTLInOut.timestamp_mu` or :meth:`artiq.coredevice.ttl.TTLInOut.sample_get`.
If the FIFO is full and another event is coming in, this causes an overflow condition.
The condition is converted into an :class:`artiq.coredevice.exceptions.RTIOOverflow` exception that is raised on a subsequent invocation of one of the readout methods (e.g. ``count()``, ``timestamp_mu()``, ``sample_get()``).

Seamless handover
-----------------

The timeline cursor persists across kernel invocations.
This is demonstrated in the following example where a pulse is split across two kernels::

  def run():
    k1()
    k2()

  @kernel
  def k1():
    ttl.on()
    delay(1*s)

  @kernel
  def k2():
    ttl.off()

Here, ``run()`` calls ``k1()`` which exits leaving the cursor one second after the rising edge and ``k2()`` then submits a falling edge at that position.

.. wavedrom::

  {
    "signal": [
      {"name": "kernel", "wave": "3.2..2..|3.", "data": ["k1: on()", "k1: delay(dt)", "k1->k2 swap", "k2: off()"], "node": "..A........B"},
      {"name": "now", "wave": "2....2...|.", "data": ["t", "t+dt"], "node": "..P........Q"},
      {},
      {},
      {"name": "rtio_counter", "wave": "x......|2xx|2", "data": ["t", "t+dt"], "node": "........V...W"},
      {"name": "ttl", "wave": "x1...0", "node": ".R...S", "phase": -7.5},
      {                                 "node": " T...U", "phase": -7.5}
    ],
    "edge": [
      "A~>R", "P~>R", "V~>R", "B~>S", "Q~>S", "W~>S",
      "R-T", "S-U", "T<->U dt"
    ]
  }


.. _rtio-handover-synchronization:

Synchronization
---------------

The seamless handover of the timeline (cursor and events) across kernels and experiments implies that a kernel can exit long before the events it has submitted have been executed.
If a previous kernel sets timeline cursor far in the future this effectively locks the system.

When a kernel should wait until all the events have been executed, use the :meth:`artiq.coredevice.core.Core.wait_until_mu` with a timestamp after (or at) the last event:

.. wavedrom::

  {
    "signal": [
      {"name": "kernel", "wave": "x3x.|5...|x", "data": ["on()", "wait_until_mu(7000)"], "node": "..A.....Y"},
      {"name": "now", "wave": "2..", "data": ["7000"], "node": "..P"},
      {},
      {},
      {"name": "rtio_counter", "wave": "x2x.|..2x..", "data": ["2000", "7000"], "node": "   ....V"},
      {"name": "ttl", "wave": "x1", "node": " R", "phase": -6.5}
    ],
    "edge": [
          "A~>R", "P~>R", "V~>R", "V~>Y"
    ]
  }

In many cases, :meth:`~artiq.language.core.now_mu` will return an appropriate timestamp::

  self.core.wait_until_mu(now_mu())


RTIO reset
-----------

The seamless handover also means that a kernel is not guaranteed to always be executed with positive slack.
An experiment can face any of these circumstances (large positive slack, full FIFOs, or negative slack).
Therefore, when switching experiments it can be adequate to clear the RTIO FIFOs and initialize the timeline cursor to "sometime in the near future" using :meth:`artiq.coredevice.core.Core.reset`.
The example idle kernel implements this mechanism.
Since it never waits for any input, it will rapidly fill the output FIFOs and would produce a large positive slack.
To avoid large positive slack and to accommodate for seamless handover the idle kernel will only run when no other experiment is pending and the example will wait before submitting events until there is significant negative slack.
