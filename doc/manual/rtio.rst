ARTIQ Real-Time I/O concepts
============================

ARTIQ's Real-Time Input-Output (RTIO) design helps achieve its goals of high timing resolution and low latency. The concepts that together form RTIO define:

  * how ARTIQ times its commands, from a user perspective;
  * how ARTIQ gets its ns-timing resolution and µs latency.

In this tutorial, our goal is to understand these RTIO concepts so that we can achieve this timing resolution and latency in the programs we'll write.

Consider a typical lab environment. One generally controls two different classes of hardware:

  * standalone hardware that interfaces with a PC; for example, a controller for an actuator;
  * hardware that interfaces the standalone hardware to the PC, such as a data acquisition (DAQ) module.

Having the second class allows for better performance than with direct control from the PC (e.g. lower latency), being purpose-built for that function(s). However, flexibility may be lost.

ARTIQ extends the flexibility of the second class of hardware. The user writes a program in Python, the program gets sent to specialized hardware, and finally the hardware executes the program. This way, we combine much better timing and latency performance of dedicated hardware with the flexibility of a Python program.

To facilitate this, ARTIQ code is composed of two program types: 

  1. Python code, executed on the *host* device (a PC);
  2. ARTIQ kernels, executed on a *core device* (an FPGA-based device).

The core device may then access specialized programmable I/O timing logic: part of the *gateware*. This allows ARTIQ kernels and Python code to invoke each other seamlessly.

To ensure the ARTIQ kernels, the gateware and the lab hardware all talk to each other seamlessly, they interface as follows. The core device's CPU sends events to a bank of FIFO (first-in-first-out) buffers, effectively queuing up events. More precisely, the FIFO holds event data and timestamps. Then, the real-time gateware receives these events from the FIFO. It's the gateware that guarantees *all or nothing* precise timing: if an event's timing isn't accurate, for example because the timestamped event was received from the CPU too late, then it isn't sent to the gateware and so isn't executed on it. Therefore, we can execute precisely timed, timestamped events.

Timeline
--------

Everything in an ARTIQ experiment occurs on a timeline. But, we must take care: it's not simply a matter of event X happening at time t1, event Y happening at time t2, and so on. The technicalities of ARTIQ infrastructure requires additional considerations for timing events properly. To give us the necessary foundations, let's define the relevant terminology:

Terminology
^^^^^^^^^^^

- **Experiment**: a sequence of timestamped events, typically defined from Python code and run on an ARTIQ kernel.
- **Timeline**: the schedule of all input and output events on all channels.
- **Wall clock**: the actual time in the real world. That is, the time we'd read if we looked at an (accurate) clock on the wall. In ARTIQ programs, this takes the value ``rtio_counter_mu``.
- **Timeline Cursor** (or simply **Cursor**): a timestamp that we move programmatically along the timeline, so that we can stamp output events with this time when they're submitted. Although, this doesn't have to be the wall clock time: it can be earlier or later. In ARTIQ programs and the kernel runtime, this timestamp takes the value ``now_mu``.
- ``mu``: machine units. These are ARTIQ's internal units of time: an integer, rather than SI units. One ``mu`` corresponds to one reference period (or clock cycle) of the system: by default and for typical core devices, this is one nanosecond (although is user-changeable). Thus, ``mu`` represents the maximum timing resolution.
- **Slack**: the difference between the timeline cursor and the wall clock.

  - **Positive slack**: the cursor is ahead of the wall clock (i.e. lies in the future).
  - **Negative slack**: the cursor is behind the wall clock (i.e. lies in the past).

Correspondingly, there are two types of events:

1. **Output events**, executed when their scheduled time matches the timeline cursor's timestamp.
2. **Input events**, timestamped when they reach the gateware (with the current wall clock value).

Due to the technical constraints of the core device, if we want deterministic and precise timing, we can't use only the wall clock. We ought to prepare timings in advance: prepare to receive inputs, and prepare to execute outputs. That's why we use the timeline cursor. We move that along the timeline programatically, and use that to precisely time when we want outputs to be executed, or want to receive inputs.

How do we move the timeline cursor? We have (Python) methods that explicitly interact with the cursor, such as :func:`artiq.language.core.delay` and :func:`artiq.language.core.delay_mu` (for delays given in SI units or machine units respectively). We also have methods run to perform an experiment, such as :func:`artiq.coredevice.ttl.TTLInOut.pulse_mu`, that advance the cursor. We can also retrieve and set the absolute value of ``now_mu`` using :meth:`artiq.language.core.now_mu()` and it can be set using :meth:`artiq.language.core.at_mu()` respectively.

Overall, respecting the technical constraints, we therefore want to build in slack so that the cursor stays ahead of the wall clock as we perform our experiment.

Let's shortly recap what timings we must consider. We have: 

- the wall clock time;
- the timeline cursor;
- and timestamps of (RTIO) events.

Now we can consider a basic example. Let's place two output events on the timeline to emit a precisely timed 2 µs pulse::

  ttl.on()
  delay(2*us)
  ttl.off()

The device ``ttl`` represents a single digital output channel (:class:`artiq.coredevice.ttl.TTLOut`). The :meth:`artiq.coredevice.ttl.TTLOut.on` method places a rising edge on the timeline at the current cursor position (``now_mu``). Then the cursor is moved forward 2 µs and a falling edge is placed at the new cursor position. Later, when the wall clock reaches the respective timestamps, the RTIO gateware executes the two events.

Let's further examine what's going on at the different levels of the software and gateware stack with the following timing diagram shows(where we've assumed ``mu`` is 1 ns):

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

Let's break down what's going on. :meth:`ttl.on() <artiq.coredevice.ttl.TTLOut.on>` places a rising edge RTIO **event** on the timeline at the current cursor position. The timeline cursor ``now_mu`` starts at 7000, and advances by 2000 after :func:`delay(2*μs) <artiq.language.core.delay>` is called. The wall clock ``rtio_counter_mu`` at the time it was processed by the ARTIQ kernel was 2600. So, the slack is 7000 - 2600 = 4400, and is positive. So now, these ``ttl`` and ``delay`` RTIO events are then safely scheduled on the core device, and finally executed when the wall clock reaches those timestamps.

In fact, this sequence is exactly equivalent to::

  ttl.pulse(2*us)

This method :meth:`artiq.coredevice.ttl.TTLOut.pulse` advances the timeline cursor (using :func:`~artiq.language.core.delay` internally) by exactly the amount given.

.. note::
  Methods such as :meth:`~artiq.coredevice.ttl.TTLOut.on`, :meth:`~artiq.coredevice.ttl.TTLOut.off`, :meth:`~artiq.coredevice.ad9914.AD9914.set`, and some other methods are *zero-duration* methods, since they do not modify the timeline cursor.

.. note::
  Wall clock time is measured as follows. Time zero is when the core device was booted up (and therefore keeps running across experiments), and we count machine units from there. For default ``mu`` and a 64-bit integer, we can therefore run ARTIQ for hundreds of years. Although, take care to avoid rounding errors: when computing the difference of absolute timestamps, use ``self.core.mu_to_seconds(t2-t1)``, not ``self.core.mu_to_seconds(t2)-self.core.mu_to_seconds(t1)`` (see :meth:`~artiq.coredevice.core.Core.mu_to_seconds`). Likewise, accumulate time in machine units and not in SI units.

.. note::
  internally, there's two types of timestamps: coarse and fine. The clock of the core device runs  the coarse resolution, with clock frequency typically 125MHz. The fine resolution timestamp allows an event to be timed with more precision. In general, ARTIQ offers precision at fine resolution, but operates at coarse resolution, affecting the behavior of some RTIO issues (e.g. sequence errors).

  .. Related: https://github.com/m-labs/artiq/issues/1237

Output errors and exceptions
----------------------------

Now that we have a better understanding of the timeline, we can understand the causes of errors that may arise in RTIO output events, as we shall detail below.

Underflows
^^^^^^^^^^

An output event must always be programmed with a timestamp in the future. That is, the timeline cursor must be later than the wall clock: ``now_mu`` > ``rtio_counter_mu``. Let’s place a rising edge event on the timeline, and raise an error if we encounter an underflow::

  try:
      ttl.on()
  except RTIOUnderflow:
      # try again at the next mains cycle
      delay(16.6667*ms)
      ttl.on()

So, if the current cursor is in the past, an :class:`artiq.coredevice.exceptions.RTIOUnderflow` exception is thrown. The experiment attempts to handle the exception by moving the cursor forward and repeating the programming of the rising edge. Once the timeline cursor has overtaken the wall clock, the exception does not reoccur and the event can be scheduled successfully. This can also be thought of as adding positive slack to the system. The following figure illustrates the two cases of error and no error:

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

To track down :class:`~artiq.coredevice.exceptions.RTIOUnderflow` exceptions in an experiment there are a few approaches:

  * Exception backtraces show where underflow has occurred while executing the code.
  * The :ref:`integrated logic analyzer <rtio-analyzer>` shows the timeline context that lead to the exception. The analyzer is always active and supports plotting of RTIO slack. This makes it possible to visually find where and how an experiment has 'run out' of positive slack.

.. _sequence-errors:

Sequence errors
^^^^^^^^^^^^^^^

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
^^^^^^^^^^
Collision errors are possible when two events have similar or same timestamps. For example, a collision occurs when events are submitted to a given RTIO output channel at a resolution the channel is not equipped to handle. Some channels implement 'replacement behavior', meaning that RTIO events submitted to the same timestamp will override each other (for example, if a ``ttl.off()`` and ``ttl.on()`` are scheduled to the same timestamp, the latter automatically overrides the former and only ``ttl.on()`` will be submitted to the channel). On the other hand, if replacement behavior is absent or disabled, or if the two events have the same coarse timestamp with differing fine timestamps, a collision error will be reported.

Like sequence errors, collisions originate in gateware and do not stop the execution of the kernel. The offending event is discarded and the problem is reported asynchronously via the core log.

Busy errors
^^^^^^^^^^^

A busy error occurs when at least one output event could not be executed because the output channel was already busy executing an event. This differs from a collision error in that a collision is triggered when a sequence of events overwhelms *communication* with a channel, and a busy error is triggered when *execution* is overwhelmed. Busy errors are only possible in the context of single events with execution times longer than a coarse RTIO clock cycle; the exact parameters will depend on the nature of the output channel (e.g. the specific peripheral device).

Offending event(s) are discarded and the problem is reported asynchronously via the core log.

Input channels and events
-------------------------

Input channels detect events, timestamp them, and place them in a buffer for the experiment to read out. The following example counts the rising edges occurring during a precisely timed 500 ns interval. If more than 20 rising edges are received, it outputs a pulse::

  if input.count(input.gate_rising(500*ns)) > 20:
      delay(2*us)
      output.pulse(500*ns)

Note that many input methods may involve the wall clock catching up to the timeline cursor or advancing later than it. We should expect this: for output events, we're planning future events, whereas for input events, we're reacting to past events.

In our example and as illustrated below, the :meth:`~artiq.coredevice.ttl.TTLInOut.gate_rising` monitors the input for rising edges during the the 500ns gate interval, recording an event for each detected edge. At the end of the interval, [:meth:`~artiq.coredevice.ttl.TTLInOut.gate_rising` exits, leaving the timeline cursor positioned at the end of the interval (` rtio_counter_mu = now_mu`). Then, [:meth:`~artiq.coredevice.ttl.TTLInOut.count` unloads these events from the input buffers and counts them, during which the wall clock advances (``rtio_counter_mu > now_mu``). Accordingly, before we place any further output events, a :func:`~artiq.language.core.delay` is necessary to re-establish positive slack.

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


|

Similar situations arise with methods such as :meth:`TTLInOut.sample_get <artiq.coredevice.ttl.TTLInOut.sample_get>` and :meth:`TTLInOut.watch_done <artiq.coredevice.ttl.TTLInOut.watch_done>`.

Overflow exceptions
^^^^^^^^^^^^^^^^^^^

Overflow exceptions occur when an RTIO input channel receives an input event when the FIFO buffer is already full. 

To understand how this happens, let us examine how input events are processed. The RTIO input channels buffer input events received while an input gate is open, or when using the sampling API (:meth:`TTLInOut.sample_input <artiq.coredevice.ttl.TTLInOut.sample_input>`) at certain points in time. The events are kept in a FIFO until the CPU reads them out via e.g. :meth:`~artiq.coredevice.ttl.TTLInOut.count`, :meth:`~artiq.coredevice.ttl.TTLInOut.timestamp_mu` or :meth:`~artiq.coredevice.ttl.TTLInOut.sample_get`. The size of these FIFOs is finite and specified in gateware; in practice, it is limited by the resources available to the FPGA, and therefore differs depending on the specific core device being used. If a FIFO is full and another event comes in, this causes an overflow condition. The condition is converted into an :class:`~artiq.coredevice.exceptions.RTIOOverflow` exception that is raised on a subsequent invocation of one of the readout methods. Overflow exceptions are generally best dealt with simply by reading out from the input buffers more frequently. In odd or particular cases, users may consider modifying the length of individual buffers in gateware.

.. note::
  It is not possible to provoke an :class:`~artiq.coredevice.exceptions.RTIOOverflow` on a RTIO output channel. While output buffers are also of finite size, and can be filled up, the CPU will simply stall the submission of further events until it is once again possible to buffer them. Among other things, this means that padding the timeline cursor with large amounts of positive slack is not always a valid strategy to avoid :class:`~artiq.coredevice.exceptions.RTIOUnderflow` exceptions when generating fast event sequences. In practice only a fixed number of events can be generated in advance, and the rest of the processing will be carried out when the wall clock is much closer to ``now_mu``.

  For larger numbers of events which run up against this restriction, the correct method is to use :ref:`getting-started-dma`. In edge cases, enabling event spreading (see below) may also be helpful. It should be carefully noted however that DMA is useful in cases where events are chronologically linear, but too closely spaced to be processed in real time; if the root of the issue is bad event *ordering,* DMA will not avoid underflows. In particular, filling up output buffers in any but the last statement of a :ref:`parallel block <getting-started-parallel>` is likely to cause underflows with or without DMA.

.. _sed-event-spreading:

Event spreading
---------------

By default, the SED only ever switches lanes for timestamp sequence reasons, as described above in :ref:`sequence-errors`. If only output events of strictly increasing coarse timestamps are queued, the SED fills up a single lane and stalls when it is full, regardless of the state of other lanes. This is preserved to avoid nondeterminism in sequence errors and corresponding unpredictable failures (since the timing of 'fullness' depends on the timing of when events are *queued*, which can vary slightly based on CPU execution jitter).

For better utilization of resources and to maximize buffering capacity, *event spreading* may be enabled, which allows the SED to switch lanes immediately when they reach a certain high watermark of 'fullness', increasing the number of events that can be queued before stalls ensue. To enable event spreading, use the ``sed_spread_enable`` config key and set it to ``1``: ::

  $ artiq_coremgmt config write -s sed_spread_enable 1

This will change where and when sequence errors occur in your kernels, and might cause them to vary from execution to execution of the same experiment. It will generally reduce or eliminate :class:`~artiq.coredevice.exceptions.RTIOUnderflow` exceptions caused by queueing stalls and significantly increase the threshold on sequence length before :ref:`DMA <getting-started-dma>` becomes necessary.

Note that event spreading can be particularly helpful in DRTIO satellites, as it is the space remaining in the *fullest* FIFO that is used as a metric for when the satellite can receive more data from the master. The setting is not system-wide and can and must be set independently for each core device in a system. In other words, to enable or disable event spreading in satellites, flash the satellite core configuration directly; this will have no effect on any other satellites or the master.

Seamless handover
-----------------

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
---------------

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