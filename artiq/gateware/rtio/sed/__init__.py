"""
The traditional RTIO system used one dedicated FIFO per output channel. While this architecture
is simple and appropriate for ARTIQ systems that were rather small and simple, it shows limitations
on more complex ones. By decreasing importance:
* with DRTIO, the master needed to keep track, for each FIFO in each satellite, a lower bound on
the number of available entries plus the last timestamp written. The timestamp is stored in order
to detect sequence errors rapidly (and allow precise exceptions without compromising performance).
When many satellites are involved, especially with DRTIO switches, the storage requirements become
prohibitive.
* with many channels in one device, the large muxes and the error detection logic that
can handle all the FIFOs make timing closure problematic.
* with many channels in one device, the FIFOs waste FPGA space, as they are never all filled at the
same time.

The scalable event dispatcher (SED) addresses those issues:
* only one lower bound on the available entries needs to be stored per satellite device for flow
control purposes (called "buffer space"). Most sequence errors no longer exist (non-increasing
timestamps into one channel are permitted to an extent) so rapid detection of them is no longer
required.
* the events can be demultiplexed to the different channels using pipeline stages that ease timing.
* only a few FIFOs are required and they are shared between the channels.

The SED core contains a configurable number of FIFOs that hold the usual information about RTIO
events (timestamp, address, data), the channel number, and a sequence number. The sequence number is
increased for each event submitted.

When an event is submitted, it is written into the current FIFO if its timestamp is strictly
increasing. Otherwise, the current FIFO number is incremented by one (and wraps around, if the
current FIFO was the last) and the event is written there, unless that FIFO already contains an
event with a greater timestamp. In that case, an asynchronous error is reported. If the destination
FIFO is full, the submitter is blocked.

In order to help spreading events among FIFOs and maximize buffering, the SED core may optionally
also switch to the next FIFO after the current FIFO has been full.

At the output of the FIFOs, the events are distributed to the channels and simultaneous events on
the same channel are handled using a structure similar to a odd-even merge-sort network that sorts
by channel. When there are simultaneous events on the same channel, the event with the highest
sequence number is kept and a flag is raised to indicate that a replacement occured on that
channel. If a replacement was made on a channel that has replacements disabled, the final
event is dropped and a collision error is reported asynchronously.

Underflow errors are detected as before by comparing the event timestamp with the current value of
the counter, and dropping events that do not have enough time to make it through the system.

The sequence number is sized to be able to represent the combined capacity of all FIFOs, plus
2 bits that allow the detection of wrap-arounds.

The maximum number of simultaneous events (on different channels), and the maximum number of active
timeline "rewinds", are equal to the number of FIFOs.

The SED logic support both synchronous and asynchronous FIFOs, which are used respectively for local
RTIO and DRTIO.

To implement flow control in DRTIO, the master queries the satellite for buffer space. The satellite
uses as buffer space the space available in its fullest FIFO.
"""
