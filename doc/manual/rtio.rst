ARTIQ Real-Time I/O concepts
============================

ARTIQ's Real-Time Input/Output design is crucial to its ability to achieve nanosecond-level high timing resolution and microsecond-scale low latency. These concepts explain:

* how commands are scheduled and executed in ARTIQ;
* the abstractions used in ARTIQ-Python code;
* the common mistakes and errors that can occur when using the system.

In a typical lab environment, two very different classes of hardware need to be controlled. One class is the vast arsenal of diverse laboratory hardware which interfaces with and is controlled from a typical PC. The other is specialized real-time hardware that requires tight coupling and a low-latency interface to a CPU. ARTIQ extends the flexibility of the second class of hardware, yielding precise, deterministic control while utilizing a dialect of Python as its control language. To accomplish these goals, ARTIQ code is composed of two types of "programs":

  1. regular Python code, executed on the *host machine* (a PC);
  2. ARTIQ :term:`kernels<kernel>`, executed on a *core device* (an FPGA-based device, usually Kasli or Kasli-SoC).

.. tip::
  This section features a glossary for ARTIQ-specific terms, which can be found by scrolling to the very bottom of the page.

The core device contains a CPU which has direct access to specialized programmable I/O timing logic, part of the *gateware.* This CPU does not send control signals to the real-time hardware directly; that would lead to imprecise, indeterminate, and generally unpredictable timing. Instead, the CPU operates at one end of a bank of FIFO (first in, first out) buffers, effectively queueing up :term:`events <output event>` to be 'fired' by the gateware at predetermined timestamps. A similar bank of FIFOs exists for :term:`input events <input event>`, storing data and timestamps for events recorded by the gateware until read out by the CPU at the other end.

This allows ARTIQ's *all or nothing* level of precision: if an event cannot be released at its predetermined time, it is not fired and the kernel will raise an exception. Control is therefore timed precisely or not at all.

Timeline and output events
--------------------------

Every action described in an ARTIQ :term:`kernel` is mapped on a timeline. Consider the following 2 µs pulse: ::

  ttl.on()
  delay(2*us)
  ttl.off()

Here the device ``ttl`` represents a single digital output channel (:class:`~artiq.coredevice.ttl.TTLOut`). The :meth:`ttl.on()<artiq.coredevice.ttl.TTLOut.on>` method places a rising edge on the timeline. The :func:`~artiq.language.core.delay` function inserts a 2 µs delay, advancing the timeline by 2 µs, and :meth:`ttl.off()<artiq.coredevice.ttl.TTLOut.off>` places a falling edge.

When a kernel is processed on a core device CPU, this mapped timeline is tracked with a counter called ``now_mu``, known as the :term:`timeline cursor`. Functions placing output events may or may not increase the counter; :meth:`~artiq.coredevice.ttl.TTLOut.on` and :meth:`~artiq.coredevice.ttl.TTLOut.off` do not, making them *zero-duration methods.*

This can be visualized with a timing diagram:

.. wavedrom::

  {
    "signal": [
      {"name": "kernel", "wave": "x32.3x", "data": ["on()", "delay(2*us)", "off()"], "node": "..A.XB"},
      {"name": "now_mu", "wave": "2...2.", "data": ["7000", "9000"], "node": "..P..Q"}
    ],
    config: {hscale: 1.5}
  }


.. for spacing reasons

\


In this example, the timeline cursor starts at 7000 mu, so the TTL rising edge is scheduled for time 7000 mu. The delay method moves the cursor forward to 9000 mu, which means the falling edge is scheduled for time 9000 mu.

..  note::
  The ARTIQ ``mu``, or :term:`machine unit`, represents the maximum resolution of RTIO timing in an ARTIQ system. Its exact duration depends on the reference period of the system, and may be changed by the user, but normally corresponds to one nanosecond.

It is important to understand that output events are *not* executed when they are processed by the CPU. Rather, they will be fired (that is, sent out from the core device's connections to real-time hardware) when the :term:`wall clock`, the *real-world time*, reaches the timestamp they were scheduled for. Meanwhile, the CPU may have progressed to an entrely different kernel. By moving the timeline cursor along the timeline programmatically, output events can be precisely scheduled without being dependent on the slow, inconsistent timings of CPU processing.

Slack
-----

In the course of an :term:`experiment`, the value of the timeline cursor may sometimes be ahead of the wall clock, sometimes behind. The difference between the timeline cursor and the wall clock time is called :term:`slack`. If the timeline cursor is ahead of the wall clock, this is called *positive slack*; if the timeline cursor is behind the wall clock, this is called *negative slack*.

Revisiting the same timing diagram:

.. wavedrom::

  {
    "signal": [
      {"name": "kernel", "wave": "x32.3x", "data": ["on()", "delay(2*us)", "off()"], "node": "..A.XB"},
      {"name": "now_mu", "wave": "2...2.", "data": ["7000", "9000"], "node": "..P..Q"},
      {},
      {"name": "slack", "wave": "x2x.2x", "data": ["4400", "5800"]},
      {},
      {"name": "rtio_counter_mu", "wave": "x2x|2x|2x2x", "data": ["2600", "3200", "7000", "9000"], "node": "       V.W"},
      {"name": "ttl", "wave": "x1.0", "node": " R.S", "phase": -6.5},
      {                               "node": " T.U", "phase": -6.5}
    ],
    "edge": [
      "A~>R", "P~>R", "V~>R", "B~>S", "Q~>S", "W~>S",
      "R-T", "S-U", "T<->U 2µs"
    ]
  }


The wall clock is represented by ``rtio_counter_mu``. In this example, the wall clock time starts at 2600, giving the experiment 4400 mu of positive slack. The three instructions take time to process and schedule, so the wall clock advances to 3200, but by this time the timeline cursor has also increased, resulting in a slack of 5800 mu. Later, when the wall clock reaches 7000 and 9000, the scheduled RTIO events are fired with precise timing.

It is quite obvious that a RTIO output event can only be scheduled for a timestamp in the future. That is, it can only be scheduled when the experiment is in a state of *positive slack.* Attempting to schedule an event for a timestamp in the past produces a :ref:`RTIO underflow <rtio-underflow>` exception.

Input channels and events
-------------------------

Input channels channels detect input events, timestamp them, and place them in a buffer for the experiment to read out. The following example counts the rising edges occurring during a precisely timed 500 ns interval. If more than 20 rising edges are received, it outputs a pulse: ::

  input.gate_rising(500*ns)
  if input.count(now_mu()) > 20:
      delay(2*us)
      output.pulse(500*ns)

More specifically, the :meth:`~artiq.coredevice.ttl.TTLInOut.gate_rising` method marks out a period of time during which rising edges on the ``input`` TTL are recorded as input events. The beginning of this period is set by the timeline cursor (i.e. it begins at ``now_mu``) and the timeline cursor is advanced by its duration (i.e., it places ``now_mu`` at the end of the 500 ns window).

.. note::
  Since :meth:`~artiq.coredevice.ttl.TTLInOut.gate_rising` cannot mark a listening period retrospectively, ``now_mu`` must be in the future; the kernel must begin in a state of positive slack.

The :meth:`~artiq.coredevice.ttl.TTLInOut.count` method unloads the input buffers and counts the input events present, up until the timestamp given as a parameter. Notably, this inherently requires *waiting for the wall clock to catch up to the time given,* for the simple reason that it's impossible to count input events which haven't happened yet. Since the parameter given is ``now_mu`` (the end of the listening period which was just defined), after :meth:`~artiq.coredevice.ttl.TTLInOut.count` the kernel is in a state of negative slack. A 2 µs delay, however, is long enough to restore positive slack, making it possible to schedule an output pulse.

The sequence is illustrated in the diagram below.

.. wavedrom::

  {
    "signal": [
      {"name": "kernel", "wave": "3..5.|2.3..x..", "data": ["gate_rising()", "count()", "delay()", "pulse()"], "node": ".A.B..C.ZD.E"},
      {"name": "now_mu", "wave": "2.2..|..2.2.", "node": ".P.Q....XV.W"},
      {},
      {},
      {"name": "input gate", "wave": "x1.0", "node": ".T.U", "phase": -2.5},
      {                                      "node": ".H.I", "phase": -2.5},
      {"name": "output", "wave": "x1.0", "node": ".R.S", "phase": -10.5},
      {                                  "node": ".L.M", "phase": -10.5}
    ],
    "edge": [
      "A~>T", "P~>T", "B~>U", "Q~>U", "U~>C", "D~>R", "E~>S", "V~>R", "W~>S",
      "T-H", "U-I", "H<->I 500ns",
      "R-L", "S-M", "L<->M 500ns"
    ]
  }

.. for spacing reasons

\

RTIO buffers are finite, and can be filled up if input events are never collected. Attempting to read an event from a buffer which has been overfilled throws a :ref:`RTIO overflow <rtio-overflows>` exception.

.. note::
  It is not possible to provoke a :class:`~artiq.coredevice.exceptions.RTIOOverflow` on a RTIO output channel. While output buffers are also of finite size, the CPU will simply stall the submission of further events until there is once again space to do so. See :ref:`rtio-overflows` for more details.

.. _rtio-handover-synchronization:

Seamless handover and synchronization
-------------------------------------

Both wall clock time and the timeline cursor persist across kernel invocations and across experiments. That is to say, in the following experiment: ::

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

the first kernel ``k1`` exits and returns to the host method, which calls a second kernel ``k2``, but the value of ``now_mu`` remains constant. This means the rising edge scheduled in ``k1`` will be followed by a falling edge on ``k2`` exactly one second later, or in other words, timing is also exact *between kernels*. The sequence is illustrated in the diagram below.

.. wavedrom::

  {
    "signal": [
      {"name": "kernel", "wave": "3.2..2..|3.", "data": ["k1: on()", "k1: delay(dt)", "k1->k2 swap", "k2: off()"], "node": "..A........B"},
      {"name": "now_mu", "wave": "2....2...|.", "data": ["t", "t+dt"], "node": "..P........Q"},
      {},
      {},
      {"name": "rtio_counter_mu", "wave": "x......|2xx|2", "data": ["t", "t+dt"], "node": "........V...W"},
      {"name": "ttl", "wave": "x1...0", "node": ".R...S", "phase": -7.5},
      {                                 "node": " T...U", "phase": -7.5}
    ],
    "edge": [
      "A~>R", "P~>R", "V~>R", "B~>S", "Q~>S", "W~>S",
      "R-T", "S-U", "T<->U dt"
    ]
  }

.. for spacing reasons

\

It should be carefully noted that, to enable this kind of seamless handover, ``k1`` exits well before all its delays have passed. In fact, a kernel is permitted to exit before *any* events it has submitted are executed. This is generally preferable: it frees up resources to the next kernel and allows work to be carried on without interruptions.

However, on the other hand, **no guarantees** are made about the state of the RTIO system when a new kernel enters. Slack may be positive, negative, or zero. Input channels might be filled to overflowing, or empty. Output channels might contain events still being executed, or scheduled to execute in the far future, or no events at all. Unexpected negative slack can cause :class:`~artiq.coredevice.exceptions.RTIOUnderflow` exceptions. Unexpected large positive slack can make a system appear 'locked', as all its events are scheduled for a distant future and the CPU stalls waiting for buffers to be emptied.

As a result, when beginning a new experiment, we often want to clear the RTIO FIFOs and initialize the timeline cursor to a reasonable point in the near future. The method :meth:`core.reset()<artiq.coredevice.core.Core.reset>` is provided for this purpose.

Correspondingly, if a kernel exits while some of its events are still waiting to be executed, there is no guarantee made that the events in question ever *will* be executed (as opposed to being flushed out by a subsequent core reset). If a kernel *should* wait until all its events have been executed, use the method :meth:`core.wait_until_mu()<artiq.coredevice.core.Core.wait_until_mu>` with a timestamp after (or at) the last event:

.. wavedrom::

  {
    "signal": [
      {"name": "kernel", "wave": "x3x.|5...|x", "data": ["on()", "wait_until_mu(7000)"], "node": "..A.....Y"},
      {"name": "now", "wave": "2..", "data": ["7000"], "node": "..P"},
      {},
      {},
      {"name": "rtio_counter_mu", "wave": "x2x.|..2x..", "data": ["2000", "7000"], "node": "   ....V"},
      {"name": "ttl", "wave": "x1", "node": " R", "phase": -6.5}
    ],
    "edge": [
          "A~>R", "P~>R", "V~>R", "V~>Y"
    ]
  }

.. for spacing reasons

\

.. tip:: 

  In many cases, :meth:`~artiq.language.core.now_mu` will return an appropriate timestamp::

    self.core.wait_until_mu(now_mu())

Output errors and exceptions
----------------------------

.. tip::
  From this point onwards, this page serves as reference material for errors, exceptions, and fine details you may encounter when working with ARTIQ RTIO. If you are just getting started with ARTIQ, and would like to start writing experiments as soon as possible, you should now have enough information to progress to the tutorial :doc:`getting_started_core`.

.. _rtio-underflow:

Underflows
^^^^^^^^^^

Since an output event can only be scheduled for a timestamp in the future, output events must always be scheduled with positive slack in the system (the timeline cursor must be later than the wall clock). Attempting to schedule an event in the past throws an :class:`~artiq.coredevice.exceptions.RTIOUnderflow` exception.

RTIO underflows can be caught and reacted to within kernel code. For example: ::

  try:
      ttl.on()
  except RTIOUnderflow:
      # try again at the next mains cycle
      delay(16.6667*ms)
      ttl.on()

If the system has run out of slack, :meth:`ttl.on()<artiq.coredevice.ttl.TTLOut.on>` will throw an underflow exception. In the code above, the experiment attempts to handle this exception by moving the cursor forward by a certain interval and trying again. If the delay has successfully reintroduced positive slack, the method will execute normally and the experiment can proceed.

To track down recurring :class:`~artiq.coredevice.exceptions.RTIOUnderflow` exceptions in an experiment there are a few approaches:

  * Exception backtraces show where underflow has occurred while executing the code.
  * The :ref:`integrated logic analyzer <rtio-analyzer>` shows the timeline context that lead to the exception. The analyzer is always active and supports plotting of RTIO slack. This makes it possible to visually find where and how an experiment has 'run out' of positive slack.

.. _sequence-errors:

Sequence errors
^^^^^^^^^^^^^^^

A sequence error occurs when a sequence of :term:`coarse timestamps` cannot be transferred to the gateware. Internally, the gateware stores output events in an array of FIFO buffers (the 'lanes'). Within each particular lane, the coarse timestamps of events must be strictly increasing.

If an event with a timestamp coarsely equal to or lesser than the previous timestamp is submitted, *or* if the current lane is nearly full, the scaleable event dispatcher (SED) selects the next lane, wrapping around once the final lane is reached. If all lanes contain an event with a timestamp equal to or later than the one being submitted, placement fails and a sequence error occurs.

.. warning::
  For performance reasons, unlike :class:`~artiq.coredevice.exceptions.RTIOUnderflow`, most gateware errors do not halt execution of the kernel, because the kernel cannot wait for potential error reports before continuing. As a result, sequence errors are not raised as exceptions and cannot be caught. Instead, the offending event -- in this case, the event that could not be queued -- is discarded, the experiment continues, and the error is reported in the core log. To check the core log, use the command ``artiq_coremgmt log``.

By default, the ARTIQ SED has eight lanes, which normally suffices to avoid sequence errors, but problems may still occur if many (>8) events are issued to the gateware with interleaving timestamps. Due to the strict timing limitations imposed on RTIO gateware, it is not possible for the SED to rearrange events in a lane once submitted, nor to anticipate future events when making lane choices. This makes sequence errors fairly 'unintelligent', but also generally fairly easy to eliminate by manually rearranging the generation of events (*not* rearranging the timing of the events themselves, which is rarely necessary.)

It is also possible to increase the number of SED lanes in the gateware, which will reduce the frequency of sequencing issues, but will correspondingly put more stress on FPGA resources and timing.

Other notes:

* Strictly increasing (coarse) timestamps never cause sequence errors.
* Strictly increasing :term:`fine timestamps` within the same coarse cycle may still cause sequence errors.
* The number of lanes is a hard limit on the number of RTIO output events that may be emitted within one coarse cycle.
* Zero-duration methods (such as :meth:`~artiq.coredevice.ttl.TTLOut.on()`) do not advance the timeline and so will always consume additional lanes if they are scheduled simultaneously. Adding a delay of at least one coarse RTIO cycle will prevent this (e.g. ``delay_mu(np.int64(self.core.ref_multiplier))``).
* Whether a particular sequence of timestamps causes a sequence error or not is fully deterministic (starting from a known RTIO state, e.g. after a reset). Adding a constant offset to the sequence will not affect the result.

.. note::
  To change the number of SED lanes, it is necessary to recompile the gateware and reflash your core device. Use the ``sed_lanes`` field in your system description file to set the value, then follow the instructions in :doc:`building_developing`. Alternatively, if you have an active firmware subscription with M-Labs, contact helpdesk@ for edited binaries.

.. _collisions-busy-errors:

Collisions
^^^^^^^^^^

Collision errors are possible when two events have similar or identical timestamps. For example, a collision occurs when events are submitted to a given RTIO output channel at a resolution the channel is not equipped to handle. Some channels implement 'replacement behavior', meaning that RTIO events submitted to the same timestamp will override each other (for example, if a ``ttl.off()`` and ``ttl.on()`` are scheduled to the same timestamp, the latter automatically overrides the former and only ``ttl.on()`` will be submitted to the channel). On the other hand, if replacement behavior is absent or disabled, or if the two events have the same coarse timestamp with differing fine timestamps, a collision error will be reported.

Like sequence errors, collisions originate in gateware and do not stop the execution of the kernel. The offending event is discarded and the problem is reported asynchronously via the core log.

Busy errors
^^^^^^^^^^^

A busy error occurs when at least one output event could not be executed because the output channel was already busy executing an event. This differs from a collision error in that a collision is triggered when a sequence of events overwhelms *communication* with a channel, and a busy error is triggered when *execution* is overwhelmed. Busy errors are only possible in the context of single events with execution times longer than a cycle of the :term:`coarse RTIO clock`; the exact parameters will depend on the nature of the output channel (e.g. the specific peripheral device).

Offending event(s) are discarded and the problem is reported asynchronously via the core log.

Input errors and exceptions
---------------------------

.. _rtio-overflows:

Overflows
^^^^^^^^^

RTIO input channels buffer input events when instructed to do so (while an input gate is open, or at intermittent points while using the sample API). These events are kept in a FIFO until the CPU reads them out with a method like :meth:`~artiq.coredevice.ttl.TTLInOut.count` or :meth:`~artiq.coredevice.ttl.TTLInOut.sample_get`. The size of these FIFOs is finite and specified in gateware; in practice, it is limited by the resources available to the FPGA.

If a FIFO is full and another input event is received, this causes an *overflow condition*. The :class:`~artiq.coredevice.exceptions.RTIOOverflow` exception itself is raised the next time the CPU attempts to read from the channel.

Overflow exceptions can be dealt with simply by reading out from the input buffers more frequently. In odd or particular cases, users may consider modifying the length of individual buffers in gateware.

.. note::
  As previously noted, it is not possible to provoke an :class:`~artiq.coredevice.exceptions.RTIOOverflow` on a RTIO output channel; the CPU will simply stall until space becomes available. In practice, this means that padding the timeline cursor with large amounts of positive slack will not always avoid :class:`~artiq.coredevice.exceptions.RTIOOverflow` exceptions when generating fast event sequences. In practice only a fixed number of events can be generated in advance, and the rest of the processing will be carried out when the wall clock is much closer to ``now_mu``.

  For larger numbers of events which run up against this restriction, the correct method is to use :ref:`getting-started-dma`. In edge cases, enabling event spreading (see below) may  also be helpful. It should be carefully noted however that DMA is useful in cases where events are chronologically linear, but too closely spaced to be processed in real time; if the root of the issue is bad event *ordering,* DMA will not avoid underflows. In particular, filling up output buffers in any but the last statement of a parallel block is likely to cause underflows with or without DMA.

.. _sed-event-spreading:

Event spreading
---------------

By default, the SED only ever switches lanes for timestamp sequence reasons, as described above in :ref:`sequence-errors`. If only output events of strictly increasing coarse timestamps are queued, the SED fills up a single lane and stalls when it is full, regardless of the state of other lanes. This is preserved to avoid nondeterminism in sequence errors and corresponding unpredictable failures (since the timing of 'fullness' depends on the timing of when events are *queued*, which can vary slightly based on CPU execution jitter).

For better utilization of resources and to maximize buffering capacity, *event spreading* may be enabled, which allows the SED to switch lanes immediately when they reach a certain high watermark of 'fullness', increasing the number of events that can be queued before stalls ensue. To enable event spreading, use the ``sed_spread_enable`` config key and set it to ``1``: ::

  $ artiq_coremgmt config write -s sed_spread_enable 1

This will change where and when sequence errors occur in your kernels, and might cause them to vary from execution to execution of the same experiment. It will generally reduce or eliminate :class:`~artiq.coredevice.exceptions.RTIOUnderflow` exceptions caused by queueing stalls and significantly increase the threshold on sequence length before :ref:`DMA <getting-started-dma>` becomes necessary.

.. note::
  Event spreading can be particularly helpful in DRTIO satellites, as it is the space remaining in the *fullest* FIFO that is used as a metric for when the satellite can receive more data from the master. The setting is not system-wide and can and must be set independently for each core device in a system. In other words, to enable or disable event spreading in satellites, flash the satellite core configuration directly; this will have no effect on any other satellites or the master.

Cursor and timestamps
---------------------

As we have already seen, the timeline cursor ``now_mu`` can be moved forward or backward on the timeline using :func:`~artiq.language.core.delay` and :func:`~artiq.language.core.delay_mu` (for delays given in SI units or machine units respectively). The absolute value of ``now_mu`` on the timeline can be retrieved using :func:`~artiq.language.core.now_mu` and set using :func:`~artiq.language.core.at_mu`. RTIO methods may be *zero-duration,* meaning that they do not affect the timeline cursor, or they may advance the timeline cursor by some amount, usually by using :func:`~artiq.language.core.delay` internally.

Absolute timestamps can be large numbers. They are represented internally by 64-bit integers. With a typical one-nanosecond machine unit, this covers a range of hundreds of years. Conversions between such a large integer number and a floating point representation can cause loss of precision through cancellation. When computing the difference of absolute timestamps, use ``self.core.mu_to_seconds(t2-t1)``, not ``self.core.mu_to_seconds(t2)-self.core.mu_to_seconds(t1)`` (see :meth:`~artiq.coredevice.core.Core.mu_to_seconds`). When accumulating time, do it in machine units and not in SI units, so that rounding errors do not accumulate.

Both the wall clock and the timeline cursor are initialized to zero at core device boot time and continue uninterrupted otherwise.

.. _rtio-coarse-fine:

Coarse and fine clocks
^^^^^^^^^^^^^^^^^^^^^^

Absolute timestamps are also referred to as *RTIO fine timestamps,* because they run on a significantly finer resolution than the timestamps of the so-called *coarse RTIO clock,* the actual clocking signal provided to or generated by the core device. The frequency of the coarse RTIO clock is set by the core device :ref:`clocking settings <core-device-clocking>` but is most commonly 125MHz, which corresponds to eight one-nanosecond machine units per coarse RTIO cycle.

The *coarse timestamp* of an event is its timestamp as according to the lower resolution of the coarse clock.   It is in practice a truncated version of the fine timestamp. In general, ARTIQ offers *precision* on the fine level, but *operates* at the coarse level; this is rarely relevant to the user, but understanding it may clarify the behavior of some RTIO issues (e.g. sequence errors).

  .. Related: https://github.com/m-labs/artiq/issues/1237

Glossary
--------
.. glossary::

  Kernel
    A method designated to run on the ARTIQ core device (rather than on the host PC), interpreted by the ARTIQ compiler.

  Experiment
    Any Python file executed on ARTIQ infrastructure, typically containing one or multiple ARTIQ kernels.

  Timeline cursor
    or ``now_mu``; a counter kept by all ARTIQ kernels which determines the timestamps for which output events are scheduled and input events are read.

  Wall clock
    or ``rtio_counter_mu``; the actual time at any moment of execution, or the time which would be read on an (accurate) clock on the wall.

  Machine unit
    The internal unit of time used by ARTIQ, representing the maximum RTIO resolution. See also :ref:`rtio-coarse-fine`.

  Output event
    Any signal fired by the RTIO system, normally an instruction sent to a piece of peripheral hardware.

  Input event
    Any signal received by the RTIO system, timestamped with wall clock time of arrival.

  Slack
    The difference between the timeline cursor and the wall clock.

  Positive slack
    The cursor is ahead of the wall clock (i.e. lies in the future).

  Negative slack
    The cursor is behind the wall clock (i.e. lies in the past).

  Coarse RTIO clock
    The actual clocking signal provided to or by the core device. Varies depending on user settings but most commonly run at 125MHz.

  Coarse timestamps
    Timestamps according to the coarse clock. See also :ref:`rtio-coarse-fine`.

  Fine timestamps
    Timestamps according to the full timing resolution of ARTIQ. See also :ref:`rtio-coarse-fine`.