Core device
===========

The core device is a FPGA-based hardware component that contains a softcore CPU tightly coupled with the so-called RTIO core that provides precision timing. The CPU executes Python code that is statically compiled by the ARTIQ compiler, and communicates with the core device peripherals (TTL, DDS, etc.) over the RTIO core. This architecture provides high timing resolution, low latency, low jitter, high level programming capabilities, and good integration with the rest of the Python experiment code.

While it is possible to use all the other parts of ARTIQ (controllers, master, GUI, result management, etc.) without a core device, many experiments require it.


.. _core-device-flash-storage:

Flash storage
*************

The core device contains some flash space that can be used to store configuration data.

This storage area is used to store the core device MAC address, IP address and even the idle kernel.

The flash storage area is one sector (typically 64 kB) large and is organized as a list of key-value records.

This flash storage space can be accessed by using ``artiq_coretool`` (see: :ref:`core-device-access-tool`).

.. _board-ports:

FPGA board ports
****************

KC705
-----

The main target board for the ARTIQ core device is the KC705 development board from Xilinx. It supports the NIST QC1 hardware via an adapter, and the NIST QC2 hardware (FMC).

With the QC1 hardware, the TTL lines are mapped as follows:

+--------------+------------+--------------+
| RTIO channel | TTL line   | Capability   |
+==============+============+==============+
| 0            | PMT0       | Input        |
+--------------+------------+--------------+
| 1            | PMT1       | Input        |
+--------------+------------+--------------+
| 2-16         | TTL0-14    | Output       |
+--------------+------------+--------------+
| 17           | SMA_GPIO_N | Input+Output |
+--------------+------------+--------------+
| 18           | LED        | Output       |
+--------------+------------+--------------+
| 19           | TTL15      | Clock        |
+--------------+------------+--------------+

Pipistrello
-----------

The low-cost Pipistrello FPGA board can be used as a lower-cost but slower alternative. The current USB over serial protocol also suffers from limitations (no monitoring/injection, no idle experiment, no kernel interruptions, lack of robustness).

When plugged to an adapter, the NIST QC1 hardware can be used. The TTL lines are mapped to RTIO channels as follows:

+--------------+----------+------------+
| RTIO channel | TTL line | Capability |
+==============+==========+============+
| 0            | PMT0     | Input      |
+--------------+----------+------------+
| 1            | PMT1     | Input      |
+--------------+----------+------------+
| 2-16         | TTL0-14  | Output     |
+--------------+----------+------------+
| 17           | EXT_LED  | Output     |
+--------------+----------+------------+
| 18           | USER_LED | Output     |
+--------------+----------+------------+
| 19           | TTL15    | Clock      |
+--------------+----------+------------+

The input only limitation on channels 0 and 1 comes from the QC-DAQ adapter. When the adapter is not used (and physically unplugged from the Pipistrello board), the corresponding pins on the Pipistrello can be used as outputs. Do not configure these channels as outputs when the adapter is plugged, as this would cause electrical contention.

The board can accept an external RTIO clock connected to PMT2. If the DDS box
does not drive the PMT2 pair, use XTRIG and patch the XTRIG transceiver output
on the adapter board onto C:15 disconnecting PMT2.
