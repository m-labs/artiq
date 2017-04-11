Distributed Real Time Input/Output (DRTIO)
==========================================

DRTIO is a time and data transfer system that allows ARTIQ RTIO channels to be distributed among several satellite devices synchronized and controlled by a central master device.

The link is a high speed duplex serial line operating at 1Gbps or more, over copper or optical fiber. Time transfer and clock recovery may be done over the serial link alone, or assisted by auxiliary signals. The DRTIO system shall be organized as much as possible to support porting to different types of transceivers (Xilinx MGTs, Altera MGTs, soft transceivers running off regular FPGA IOs, etc.) and different synchronization mechanisms.

The main source of DRTIO traffic is the remote control of RTIO output and input channels. The protocol shall be optimized to maximize throughput and minimize latency, and shall handle flow control and error conditions (underflows, overflows, etc.)

The DRTIO protocol shall also support auxiliary, low-priority and non-realtime traffic. The auxiliary channel shall support overriding and monitoring TTL I/Os. Auxiliary traffic shall never interrupt or delay the main traffic, so that it cannot cause unexpected poor performance (e.g. RTIO underflows).

The lower layers of DRTIO are similar to White Rabbit, with the following main differences: ::
* lower latency
* deterministic latency
* real-time/auxiliary channels
* higher bandwidth
* no Ethernet compatibility
* only star or tree topologies are supported

From ARTIQ kernels, DRTIO channels are used in the same way as local RTIO channels.
