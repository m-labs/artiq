Distributed Real Time Input/Output (DRTIO)
==========================================

DRTIO is a time and data transfer system that allows ARTIQ RTIO channels to be distributed among several satellite devices synchronized and controlled by a central core device.

The link is a high speed duplex serial line operating at 1Gbps or more, over copper or optical fiber.

The main source of DRTIO traffic is the remote control of RTIO output and input channels. The protocol is optimized to maximize throughput and minimize latency, and handles flow control and error conditions (underflows, overflows, etc.)

The DRTIO protocol also supports auxiliary, low-priority and non-realtime traffic. The auxiliary channel supports overriding and monitoring TTL I/Os. Auxiliary traffic never interrupts or delays the main traffic, so that it cannot cause unexpected poor performance (e.g. RTIO underflows).

Time transfer and clock syntonization is typically done over the serial link alone. The DRTIO code is organized as much as possible to support porting to different types of transceivers (Xilinx MGTs, Altera MGTs, soft transceivers running off regular FPGA IOs, etc.) and different synchronization mechanisms.

The lower layers of DRTIO are similar to White Rabbit, with the following main differences:

* lower latency
* deterministic latency
* real-time/auxiliary channels
* higher bandwidth
* no Ethernet compatibility
* only star or tree topologies are supported

From ARTIQ kernels, DRTIO channels are used in the same way as local RTIO channels.

.. _using-drtio:

Using DRTIO
-----------

Terminology
+++++++++++

In a system of interconnected DRTIO devices, each RTIO core (driving RTIO PHYs; for example a RTIO core would connect to a large bank of TTL signals) is assigned a number and is called a *destination*. One DRTIO device normally contains one RTIO core.

On one DRTIO device, the immediate path that a RTIO request must take is called a *hop*: the request can be sent to the local RTIO core, or to another device downstream. Each possible hop is assigned a number. Hop 0 is normally the local RTIO core, and hops 1 and above correspond to the respective downstream ports of the device.

DRTIO devices are arranged in a tree topology, with the core device at the root. For each device, its distance from the root (in number of devices that are crossed) is called its *rank*. The root has rank 0, the devices immediately connected to it have rank 1, and so on.

The routing table
+++++++++++++++++

The routing table defines, for each destination, the list of hops ("route") that must be taken from the root in order to reach it.

It is stored in a binary format that can be manipulated with the :ref:`artiq_route utility <routing-table-tool>`. The binary file is then programmed into the flash storage of the core device under the ``routing_table`` key. It is automatically distributed to downstream devices when the connections are established. Modifying the routing table requires rebooting the core device for the new table to be taken into account.

All routes must end with the local RTIO core of the last device (0).

The local RTIO core of the core device is a destination like any other, and it needs to be explicitly part of the routing table for kernels to be able to access it.

If no routing table is programmed, the core device takes a default routing table for a star topology (i.e. with no devices of rank 2 or above), with destination 0 being the core device's local RTIO core and destinations 1 and above corresponding to devices on the respective downstream ports.

Here is an example of creating and programming a routing table for a chain of 3 devices: ::

    # create an empty routing table
    $ artiq_route rt.bin init

    # set destination 0 to the local RTIO core
    $ artiq_route rt.bin set 0 0

    # for destination 1, first use hop 1 (the first downstream port)
    # then use the local RTIO core of that second device.
    $ artiq_route rt.bin set 1 1 0

    # for destination 2, use hop 1 and reach the second device as
    # before, then use hop 1 on that device to reach the third
    # device, and finally use the local RTIO core (hop 0) of the
    # third device.
    $ artiq_route rt.bin set 2 1 1 0

    $ artiq_route rt.bin show
      0:   0
      1:   1   0
      2:   1   1   0

    $ artiq_coremgmt config write -f routing_table rt.bin

Addressing distributed RTIO cores from kernels
++++++++++++++++++++++++++++++++++++++++++++++

Remote RTIO channels are accessed in the same way as local ones. Bits 16-24 of the RTIO channel number define the destination. Bits 0-15 of the RTIO channel number select the channel within the destination.

Link establishment
++++++++++++++++++

After devices have booted, it takes several seconds for all links in a DRTIO system to become established (especially with the long locking times of low-bandwidth PLLs that are used for jitter reduction purposes). Kernels should not attempt to access destinations until all required links are up (when this happens, the ``RTIODestinationUnreachable`` exception is raised). ARTIQ provides the method :meth:`~artiq.coredevice.core.Core.get_rtio_destination_status` that determines whether a destination can be reached. We recommend calling it in a loop in your startup kernel for each important destination, to delay startup until they all can be reached.

Latency
+++++++

Each hop increases the RTIO latency of a destination by a significant amount; that latency is however constant and can be compensated for in kernels. To limit latency in a system, fully utilize the downstream ports of devices to reduce the depth of the tree, instead of creating chains.

Internal details
----------------

Real-time and auxiliary packets
+++++++++++++++++++++++++++++++

DRTIO is a packet-based protocol that uses two types of packets:

* real-time packets, which are transmitted at high priority at a high bandwidth and are used for the bulk of RTIO commands and data. In the ARTIQ DRTIO implementation, real-time packets are processed entirely in gateware.
* auxiliary packets, which are lower-bandwidth and are used for ancillary tasks such as housekeeping and monitoring/injection. Auxiliary packets are low-priority and their transmission has no impact on the timing of real-time packets (however, transmission of real-time packets slows down the transmission of auxiliary packets). In the ARTIQ DRTIO implementation, the contents of the auxiliary packets are read and written directly by the firmware, with the gateware simply handling the transmission of the raw data.

Link layer
++++++++++

The lower layer of the DRTIO protocol stack is the link layer, which is responsible for delimiting real-time and auxiliary packets, and assisting with the establishment of a fixed-latency high speed serial transceiver link.

DRTIO uses the IBM (Widmer and Franaszek) 8b/10b encoding. D characters (the encoded 8b symbols) always transmit real-time packet data, whereas K characters are used for idling and transmitting auxiliary packet data.

At every logic clock cycle, the high-speed transceiver hardware transmits some amount N of 8b/10b characters (typically, N is 2 or 4) and receives the same amount. With DRTIO, those characters must be all of the D type or all of the K type; mixing D and K characters in the same logic clock cycle is not allowed.

A real-time packet is defined by a series of D characters containing the packet's payload, delimited by at least one K character. Real-time packets must be padded to satisfy the requirement that only D or only K characters are transmitted during a logic clock cycle, by making their length a multiple of N.

K characters, which are transmitted whenever there is no real-time data to transmit and to delimit real-time packets, are chosen using a 3-bit K selection word. If this K character is the first character in the set of N characters processed by the transceiver in the logic clock cycle, the mapping between the K selection word and the 8b/10b K space contains commas. If the K character is any of the subsequent characters processed by the transceiver, a different mapping is used that does not contain any commas. This scheme allows the receiver to align its logic clock with that of the transmitter, simply by shifting its logic clock so that commas are received into the first character position.

.. note:: Due to the shoddy design of transceiver hardware, this simple process of clock and comma alignment is difficult to perform in practice. The paper "High-speed, fixed-latency serial links with Xilinx FPGAs" (by Xue LIU, Qing-xu DENG, Bo-ning HOU and Ze-ke WANG) discusses techniques that can be used. The ARTIQ implementation simply keeps resetting the receiver until the comma is aligned, since relatively long lock times are acceptable.

The series of K selection words is then used to form auxiliary packets and the idle pattern. When there is no auxiliary packet to transfer or to delimitate auxiliary packets, the K selection word ``100`` is used. To transfer data from an auxiliary packet, the K selection word ``0ab`` is used, with ``ab`` containing two bits of data from the packet. An auxiliary packet is delimited by at least one ``100`` K selection word.

Both real-time traffic and K selection words are scrambled in order to make the generated electromagnetic interference practically independent from the DRTIO traffic. A multiplicative scrambler is used and its state is shared between the real-time traffic and K selection words, so that real-time data can be descrambled immediately after the scrambler has been synchronized from the K characters. Another positive effect of the scrambling is that commas always appear regularly in the absence of any traffic (and in practice also appear regularly on a busy link). This makes a receiver always able to synchronize itself to an idling transmitter, which removes the need for relatively complex link initialization states.

Due to the use of K characters both as delimiters for real-time packets and as information carrier for auxiliary packets, auxiliary traffic is guaranteed a minimum bandwidth simply by having a maximum size limit on real-time packets.

Clocking
++++++++

At the DRTIO satellite device, the recovered and aligned transceiver clock is used for clocking RTIO channels, after appropriate jitter filtering using devices such as the Si5324. The same clock is also used for clocking the DRTIO transmitter (loop timing), which simplifies clock domain transfers and allows for precise round-trip-time measurements to be done.

RTIO clock synchronization
++++++++++++++++++++++++++

As part of the DRTIO link initialization, a real-time packet is sent by the core device to each satellite device to make them load their respective timestamp counters with the timestamp values from their respective packets.

RTIO outputs
++++++++++++

Controlling a remote RTIO output involves placing the RTIO event into the buffer of the destination. The core device maintains a cache of the buffer space available in each destination. If, according to the cache, there is space available, then a packet containing the event information (timestamp, address, channel, data) is sent immediately and the cached value is decremented by one. If, according to the cache, no space is available, then the core device sends a request for the space available in the destination and updates the cache. The process repeats until at least one remote buffer entry is available for the event, at which point a packet containing the event information is sent as before.

Detecting underflow conditions is the responsibility of the core device; should an underflow occur then no DRTIO packet is transmitted. Sequence errors are handled similarly.

RTIO inputs
+++++++++++

The core device sends a request to the satellite for reading data from one of its channels. The request contains a timeout, which is the RTIO timestamp to wait for until an input event appears. The satellite then replies with either an input event (containing timestamp and data), a timeout, or an overflow error.
