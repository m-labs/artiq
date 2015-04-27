FPGA board ports
================

KC705
-----

The main target board for the ARTIQ core device is the KC705 development board from Xilinx.

Pipistrello
-----------

The low-cost Pipistrello FPGA board can be used as a lower-cost but slower alternative.

When plugged to an adapter, the NIST QC1 hardware can be used. The TTL lines are mapped to RTIO channels as follows:

+--------------+----------+-----------------+
| RTIO channel | TTL line | Capability      |
+==============+==========+=================+
| 0            | PMT0     | Input only      |
+--------------+----------+-----------------+
| 1            | PMT1     | Input only      |
+--------------+----------+-----------------+
| 2-18         | TTL0-16  | Output only     |
+--------------+----------+-----------------+
| 19-21        | LEDs     | Output only     |
+--------------+----------+-----------------+
| 22           | TTL2     | Output only     |
+--------------+----------+-----------------+

The input only limitation on channels 0 and 1 comes from the QC-DAQ adapter. When the adapter is not used (and physically unplugged from the Pipistrello board), the corresponding pins on the Pipistrello can be used as outputs. Do not configure these channels as outputs when the adapter is plugged, as this would cause electrical contention.

The board can accept an external RTIO clock connected to PMT2.
