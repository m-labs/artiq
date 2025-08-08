ARTIQ Real-Time I/O concepts
============================

What is ARTIQ Real-Time I/O?
----------------------------

ARTIQ's Real-Time Input-Output (RTIO) design helps achieve its goals of high timing resolution and low latency. The concepts that together form RTIO define:

  * how ARTIQ times its commands, from a user perspective;
  * how ARTIQ gets its ns-timing resolution and µs latency.

Taking a high-level perspective, consider the two different classes of hardware we wish to control in a typical lab:

  * standalone hardware that interfaces with a PC; for example, a controller for an actuator;
  * hardware that interfaces the standalone hardware to the PC, such as a data acquisition (DAQ) module.

ARTIQ extends the flexibility of the second class of hardware, yielding both better timing performance and determinism compared to direct control from the PC, all while utilizing a subset of Python rather than a lower-level language.

To facilitate this, ARTIQ code is composed of two program types: 

  1. Python code, executed on the *host* device (a PC);
  2. ARTIQ :term:`kernels<kernel>`, executed on a *core device* (an FPGA-based device).

The core device may then access the *gateware*: specialized programmable I/O timing logic. Thus, ARTIQ's Real-Time I/O constitutes a seamless interface between Python code, ARTIQ kernels, gateware and lab hardware.

The interface itself is as follows. The core device's CPU sends events to a bank of FIFO (first-in-first-out) buffers, effectively queuing up these events and holding timestamps for them. Then, the gateware receives these events from the FIFO. It is the gateware that guarantees *all or nothing* precise timing: if an event's timing is not accurate, for example because the timestamped event was received from the CPU too late, then it is not sent to the gateware and so is not executed on it. Altogether, we can execute precisely timed, deterministic events.

RTIO concepts - basics
----------------------

Timeline and output events
^^^^^^^^^^^^^^^^^^^^^^^^^^

Everything in an :term:`ARTIQ experiment<Experiment>` occurs on a :term:`timeline`. Consider the following 2 µs pulse::

  ttl.on()
  delay(2*us)
  ttl.off()

where the device ``ttl`` represents a single digital output channel (:class:`artiq.coredevice.ttl.TTLOut`). The :meth:`artiq.coredevice.ttl.TTLOut.on` method places a rising edge on the timeline. Following the 2 µs delay from :func:`artiq.language.core.delay`), :meth:`ttl.off()<artiq.coredevice.ttl.TTLOut.off>` places a falling edge. These events may be visualized using a timing diagram:

.. wavedrom::

  {
    "signal": [
      {"name": "kernel", "wave": "x32.3x", "data": ["on()", "delay(2*us)", "off()"], "node": "..A.XB"},
      {"name": "now_mu", "wave": "2...2.", "data": ["7000", "9000"], "node": "..P..Q"}
    ],
    config: {hscale: 1.5}
  }

On the :term:`kernel`, the events in yellow are :term:`output events<Output event>`. Calling kernel methods for output events submits them to the core device, where they are timestamped with the current position on the timeline. This position is known as the :term:`timeline cursor` and takes the value ``now_mu``. In this example, the cursor starts at 7000, while a rising edge is placed; :func:`delay(2*us)<artiq.language.core.delay>` moves it to 9000; and a falling edge is placed at the new cursor position. Here, ARTIQ's internal :term:`machine units<Machine unit>`, or ``mu``, take a value corresponding to 1 ns.

However, output events are not executed immediately upon being received by the core device. Rather, only when the :term:`wall clock`, or real-world time, reaches a timestamp does the gateware execute the respective event. Technical constraints of the core device prevent us from relying only on the wall clock for timings of events.

Instead of relying on the wall clock, we can ensure deterministic and precise timing by preparing event timings in advance: namely, preparing to receive inputs and preparing to execute outputs. Thus, by moving the timeline cursor along the timeline programatically, we may precisely time when we want outputs to be executed, or inputs to be received.

Slack
^^^^^

A consequence of the wall clock and timeline cursor not being the same is that if we schedule output events while the cursor is lagging behind the wall clock, the output events will never occur. This implies that we should build in :term:`slack` such that the cursor stays ahead of the wall clock as we perform our experiment.

Let us further expand the previous timing diagram to examine the different levels of the software and gateware stack:

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

The wall clock takes the value ``rtio_counter_mu``. In this example, its value was 2600 at the time the rising edge event was processed by the ARTIQ kernel. The timeline cursor ``now_mu`` was at 7000. So, the slack was 7000 - 2600 = 4400, which is :term:`positive<Positive slack>`. Then, the ``ttl`` and ``delay`` RTIO events are safely scheduled on the core device, and finally executed when the wall clock reaches those timestamps.

.. note::
  This experiment sequence is exactly equivalent to::

    ttl.pulse(2*us)

  using the function :func:`artiq.coredevice.ttl.TTLOut.pulse`.

Input channels and events
^^^^^^^^^^^^^^^^^^^^^^^^^

Input channels detect :term:`input events<Input event>` and place them in a buffer on the core device to read out for the experiment. These are timestamped by the wall clock when they are received, but cannot be read out from the buffer immediately.

The following example counts the rising edges occurring during a precisely timed 500 ns interval. If more than 20 rising edges are received, it outputs a pulse::

  if input.count(input.gate_rising(500*ns)) > 20:
      delay(2*us)
      output.pulse(500*ns)

Note that many input methods may involve the wall clock catching up to the timeline cursor or advancing later than it, leaving us in :term:`negative slack`. We should expect this: for output events, we're planning future events, whereas for input events, we're reacting to past events. Let us illustrate the example:

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


Here, :meth:`~artiq.coredevice.ttl.TTLInOut.gate_rising` monitors the input for rising edges during the the 500ns input gate (or gate window), recording an event for each detected edge. At the end of this window, :meth:`~artiq.coredevice.ttl.TTLInOut.gate_rising` exits, leaving the timeline cursor positioned at the end of the window (``rtio_counter_mu = now_mu``). Then, :meth:`~artiq.coredevice.ttl.TTLInOut.count` unloads these events from the input buffers and counts them. But, since this takes a finite time, the wall clock advances (``rtio_counter_mu > now_mu``). Accordingly, before we place :func:`pulse()<artiq.coredevice.ttl.TTLOut.pulse>`, which is an output event, we must use :func:`~artiq.language.core.delay` to re-establish positive slack.

.. note::
  Similar situations arise with methods such as :meth:`TTLInOut.sample_get <artiq.coredevice.ttl.TTLInOut.sample_get>` and :meth:`TTLInOut.watch_done <artiq.coredevice.ttl.TTLInOut.watch_done>`.

RTIO concepts - reference
-------------------------

Cursor and timings
^^^^^^^^^^^^^^^^^^

In order to build in :term:`slack`, we must move the :term:`timeline cursor` accordingly. We have seen already that :func:`artiq.language.core.delay` explicitly interacts with the cursor. :func:`artiq.language.core.delay_mu` delays by machine units rather than SI units. In addition, some methods that schedule events in order to perform an experiment, such as :func:`artiq.coredevice.ttl.TTLOut.pulse`, also advance the cursor by using :func:`~artiq.language.core.delay` internally. We can also retrieve and set the cursor's absolute value using :meth:`artiq.language.core.now_mu()` and :meth:`artiq.language.core.at_mu()` respectively.

.. note::
  Methods such as :meth:`~artiq.coredevice.ttl.TTLOut.on`, :meth:`~artiq.coredevice.ttl.TTLOut.off`, :meth:`~artiq.coredevice.ad9914.AD9914.set`, and some other methods are *zero-duration* methods, since they do not modify the timeline cursor.

.. note::
  Wall clock time is measured as follows. Time zero is when the core device was booted up (and therefore keeps running across experiments), and we count machine units from there. For default ``mu`` and a 64-bit integer, we can therefore run ARTIQ for hundreds of years. Although, take care to avoid rounding errors: when computing the difference of absolute timestamps, use ``self.core.mu_to_seconds(t2-t1)``, not ``self.core.mu_to_seconds(t2)-self.core.mu_to_seconds(t1)`` (see :meth:`~artiq.coredevice.core.Core.mu_to_seconds`). Likewise, accumulate time in machine units and not in SI units.

.. note::
  Internally, there are two types of timestamps: coarse and fine. The clock of the core device runs at coarse resolution, with clock frequency typically 125MHz. The fine resolution timestamp allows an event to be timed with more precision. In general, ARTIQ offers precision at fine resolution, but operates at coarse resolution, affecting the behavior of some RTIO issues (e.g. sequence errors).

  .. Related: https://github.com/m-labs/artiq/issues/1237

Output errors and exceptions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Underflows
""""""""""

Since an output event must always be programmed with a timestamp in the future, the timeline cursor must be later than the wall clock: ``now_mu`` > ``rtio_counter_mu``. Let us place a rising edge event on the timeline, and raise an error if we encounter an underflow::

  try:
      ttl.on()
  except RTIOUnderflow:
      # try again at the next mains cycle
      delay(16.6667*ms)
      ttl.on()

So, if the current cursor is in the past, an :class:`artiq.coredevice.exceptions.RTIOUnderflow` exception is thrown. ARTIQ attempts to handle the exception by moving the cursor forward and repeating the programming of the rising edge. Once the timeline cursor has overtaken the wall clock, the exception does not reoccur and the event can be scheduled successfully. This can also be thought of as adding positive slack to the system. The following figure illustrates the two cases of error and no error:

.. wavedrom::

  {
    "signal": [
      {"name": "kernel", "wave": "x34..2.3x", "data": ["on()", "RTIOUnderflow", "delay()", "on()"], "node": "..AB....C", "phase": -3},
      {"name": "now_mu", "wave": "2.....2", "data": ["t0", "t1"], "node": ".D.....E", "phase": -4},
      {},
      {"name": "slack", "wave": "2x....2", "data": ["< 0", "> 0"], "node": ".T", "phase": -4},
      {},
      {"name": "rtio_counter", "wave": "x2x.2x....2x2", "data": ["t0", "> t0", "< t1", "t1"], "node": "............P"},
      {"name": "ttl", "wave": "x...........1", "node": ".R..........S", "phase": -0.5}
    ],
    "edge": [
      "A-~>R forbidden", "D-~>R", "T-~B exception",
      "C~>S allowed", "E~>S", "P~>S"
    ]
  }

To track down :class:`~artiq.coredevice.exceptions.RTIOUnderflow` exceptions in an experiment there are a few approaches:

  * Exception backtraces show where underflow has occurred while executing the code.
  * The :ref:`integrated logic analyzer <rtio-analyzer>` shows the timeline context that lead to the exception. The analyzer is always active and supports plotting of RTIO slack. This makes it possible to visually find where and how an experiment has 'run out' of positive slack.

.. _sequence-errors:

Sequence errors
"""""""""""""""

A sequence error occurs when a sequence of coarse timestamps cannot be transferred to the gateware. Internally, the gateware stores output events in an array of FIFO buffers (the 'lanes'). Within each particular lane, the coarse timestamps of events must be strictly increasing.

If an event with a timestamp coarsely equal to or lesser than the previous timestamp is submitted, *or* if the current lane is nearly full, the scaleable event dispatcher (SED) selects the next lane, wrapping around once the final lane is reached. If this lane also contains an event with a timestamp equal to or later than the one being submitted, the placement fails and a sequence error occurs.

.. note::
  For performance reasons, unlike :class:`~artiq.coredevice.exceptions.RTIOUnderflow`, most gateware errors do not halt execution of the kernel, because the kernel cannot wait for potential error reports before continuing. As a result, sequence errors are not raised as exceptions and cannot be caught. Instead, the offending event -- in this case, the event that could not be queued -- is discarded, the experiment continues, and the error is reported in the core log. To check the core log, use the command ``artiq_coremgmt log``.

By default, the ARTIQ SED has eight lanes, which normally suffices to avoid sequence errors, but problems may still occur if many (>8) events are issued to the gateware with interleaving timestamps. Due to the strict timing limitations imposed on RTIO gateware, it is not possible for the SED to rearrange events in a lane once submitted, nor to anticipate future events when making lane choices. This makes sequence errors fairly 'unintelligent', but also generally fairly easy to eliminate by manually rearranging the generation of events (*not* rearranging the timing of the events themselves, which is rarely necessary.)

It is also possible to increase the number of SED lanes in the gateware, which will reduce the frequency of sequencing issues, but will correspondingly put more stress on FPGA resources and timing.

Other notes:

* Strictly increasing (coarse) timestamps never cause sequence errors.
* Strictly increasing *fine* timestamps within the same coarse cycle may still cause sequence errors.
* The number of lanes is a hard limit on the number of RTIO output events that may be emitted within one coarse cycle.
* Zero-duration methods (such as :meth:`artiq.coredevice.ttl.TTLOut.on()`) do not advance the timeline and so will always consume additional lanes if they are scheduled simultaneously. Adding a delay of at least one coarse RTIO cycle will prevent this (e.g. ``delay_mu(np.int64(self.core.ref_multiplier))``).
* Whether a particular sequence of timestamps causes a sequence error or not is fully deterministic (starting from a known RTIO state, e.g. after a reset). Adding a constant offset to the sequence will not affect the result.

.. note::
  To change the number of SED lanes, it is necessary to recompile the gateware and reflash your core device. Use the ``sed_lanes`` field in your system description file to set the value, then follow the instructions in :doc:`building_developing`. Alternatively, if you have an active firmware subscription with M-Labs, contact helpdesk@ for edited binaries.

.. _collisions-busy-errors:

Collisions
""""""""""
Collision errors are possible when two events have similar or same timestamps. For example, a collision occurs when events are submitted to a given RTIO output channel at a resolution the channel is not equipped to handle. Some channels implement 'replacement behavior', meaning that RTIO events submitted to the same timestamp will override each other (for example, if a ``ttl.off()`` and ``ttl.on()`` are scheduled to the same timestamp, the latter automatically overrides the former and only ``ttl.on()`` will be submitted to the channel). On the other hand, if replacement behavior is absent or disabled, or if the two events have the same coarse timestamp with differing fine timestamps, a collision error will be reported.

Like sequence errors, collisions originate in gateware and do not stop the execution of the kernel. The offending event is discarded and the problem is reported asynchronously via the core log.

Busy errors
"""""""""""

A busy error occurs when at least one output event could not be executed because the output channel was already busy executing an event. This differs from a collision error in that a collision is triggered when a sequence of events overwhelms *communication* with a channel, and a busy error is triggered when *execution* is overwhelmed. Busy errors are only possible in the context of single events with execution times longer than a coarse RTIO clock cycle; the exact parameters will depend on the nature of the output channel (e.g. the specific peripheral device).

Offending event(s) are discarded and the problem is reported asynchronously via the core log.

Input errors and exceptions
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Overflows
"""""""""

Overflow exceptions occur when an RTIO input channel receives an input event when the FIFO buffer is already full. 

To understand how this happens, let us examine how input events are processed. The RTIO input channels buffer input events received while an input gate is open, or when using the sampling API (:meth:`TTLInOut.sample_input <artiq.coredevice.ttl.TTLInOut.sample_input>`) at certain points in time. The events are kept in a FIFO until the CPU reads them out via e.g. :meth:`~artiq.coredevice.ttl.TTLInOut.count`, :meth:`~artiq.coredevice.ttl.TTLInOut.timestamp_mu` or :meth:`~artiq.coredevice.ttl.TTLInOut.sample_get`. The size of these FIFOs is finite and specified in gateware; in practice, it is limited by the resources available to the FPGA, and therefore differs depending on the specific core device being used. If a FIFO is full and another event comes in, this causes an overflow condition. The condition is converted into an :class:`~artiq.coredevice.exceptions.RTIOOverflow` exception that is raised on a subsequent invocation of one of the readout methods. Overflow exceptions are generally best dealt with simply by reading out from the input buffers more frequently. In odd or particular cases, users may consider modifying the length of individual buffers in gateware.

.. note::
  It is not possible to provoke an :class:`~artiq.coredevice.exceptions.RTIOOverflow` on a RTIO output channel. While output buffers are also of finite size, and can be filled up, the CPU will simply stall the submission of further events until it is once again possible to buffer them. Among other things, this means that padding the timeline cursor with large amounts of positive slack is not always a valid strategy to avoid :class:`~artiq.coredevice.exceptions.RTIOOverflow` exceptions when generating fast event sequences. In practice only a fixed number of events can be generated in advance, and the rest of the processing will be carried out when the wall clock is much closer to ``now_mu``.

  For larger numbers of events which run up against this restriction, the correct method is to use :ref:`getting-started-dma`. In edge cases, enabling event spreading (see below) may also be helpful. It should be carefully noted however that DMA is useful in cases where events are chronologically linear, but too closely spaced to be processed in real time; if the root of the issue is bad event *ordering,* DMA will not avoid underflows. In particular, filling up output buffers in any but the last statement of a :ref:`parallel block <getting-started-parallel>` is likely to cause underflows with or without DMA.

.. _sed-event-spreading:

Event spreading
^^^^^^^^^^^^^^^

By default, the SED only ever switches lanes for timestamp sequence reasons, as described above in :ref:`sequence-errors`. If only output events of strictly increasing coarse timestamps are queued, the SED fills up a single lane and stalls when it is full, regardless of the state of other lanes. This is preserved to avoid nondeterminism in sequence errors and corresponding unpredictable failures (since the timing of 'fullness' depends on the timing of when events are *queued*, which can vary slightly based on CPU execution jitter).

For better utilization of resources and to maximize buffering capacity, *event spreading* may be enabled, which allows the SED to switch lanes immediately when they reach a certain high watermark of 'fullness', increasing the number of events that can be queued before stalls ensue. To enable event spreading, use the ``sed_spread_enable`` config key and set it to ``1``: ::

  $ artiq_coremgmt config write -s sed_spread_enable 1

This will change where and when sequence errors occur in your kernels, and might cause them to vary from execution to execution of the same experiment. It will generally reduce or eliminate :class:`~artiq.coredevice.exceptions.RTIOUnderflow` exceptions caused by queueing stalls and significantly increase the threshold on sequence length before :ref:`DMA <getting-started-dma>` becomes necessary.

Note that event spreading can be particularly helpful in DRTIO satellites, as it is the space remaining in the *fullest* FIFO that is used as a metric for when the satellite can receive more data from the master. The setting is not system-wide and can and must be set independently for each core device in a system. In other words, to enable or disable event spreading in satellites, flash the satellite core configuration directly; this will have no effect on any other satellites or the master.

Seamless handover
^^^^^^^^^^^^^^^^^

The timeline cursor persists across kernel invocations. This is demonstrated in the following example where a pulse is split across two kernels::

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
.. _rtio-handover-synchronization:

Synchronization
^^^^^^^^^^^^^^^

The seamless handover of the timeline (cursor and events) across kernels and experiments implies that a kernel can exit long before the events it has submitted have been executed. Generally, this is preferable: it frees up resources to the next kernel and allows work to be carried on from kernel to kernel without interruptions.

However, as a result, no guarantees are made about the state of the system when a new kernel enters. Slack may be positive, negative, or zero; input channels may be filled to overflowing, or empty; output channels may contain events currently being executed, contain events scheduled for the far future, or contain no events at all. Unexpected negative slack can cause RTIOUnderflows. Unexpected large positive slack may cause a system to appear to 'lock', as all its events are scheduled for a distant future and the CPU must wait for the output buffers to empty to continue.

As a result, when beginning a new experiment in an uncertain context, we often want to clear the RTIO FIFOs and initialize the timeline cursor to a reasonable point in the near future. The method :meth:`artiq.coredevice.core.Core.reset` (``self.core.reset()``) is provided for this purpose. The example idle kernel implements this mechanism.

On the other hand, if a kernel exits while some of its events are still waiting to be executed, there is no guarantee made that the events in question ever *will* be executed (as opposed to being flushed out by a subsequent core reset). If a kernel should wait until all its events have been executed, use the method :meth:`~artiq.coredevice.core.Core.wait_until_mu` with a timestamp after (or at) the last event:

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

In many cases, :meth:`~artiq.language.core.now_mu` will return an appropriate timestamp::

  self.core.wait_until_mu(now_mu())

Glossary
--------
.. glossary::

  Kernel
    A method that runs on the ARTIQ core device (rather than on the host PC).
  
  Experiment
    A sequence of timestamped events, typically defined from Python code and run on an ARTIQ kernel.

  Timeline
    The schedule of all input and output events on all channels.

  Timeline Cursor
    A timestamp that we move programmatically along the timeline, so that we can stamp output events with this time when they're submitted. Although, this does not have to be the wall clock time: it can be earlier or later. In ARTIQ programs and the kernel runtime, this timestamp takes the value ``now_mu``.

  Output event
    Event executed when its scheduled time matches the timeline cursor's timestamp.

  Input event
    Event timestamped when it reaches the gateware (with the current wall clock value).

  Wall clock
    The actual time in the real world. That is, the time we'd read if we looked at an (accurate) clock on the wall. In ARTIQ programs, this takes the value ``rtio_counter_mu``.

  Machine unit
    ARTIQ's internal unit of time, and which takes the value ``mu``: an integer, rather than SI units. One ``mu`` corresponds to one reference period (or clock cycle) of the system: by default and for typical core devices, this is one nanosecond (although is user-changeable). Thus, ``mu`` represents the maximum timing resolution.

  Slack
    The difference between the timeline cursor and the wall clock.

  Positive slack
    The cursor is ahead of the wall clock (i.e. lies in the future).

  Negative slack
    The cursor is behind the wall clock (i.e. lies in the past).

