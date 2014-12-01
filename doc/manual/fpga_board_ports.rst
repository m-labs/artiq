FPGA board ports
================

KC705
-----

The main target board for the ARTIQ core device is the KC705 development board from Xilinx.

Papilio Pro
-----------

The low-cost Papilio Pro FPGA board can be used with some limitations.

When plugged to a QC-DAQ LVDS adapter, the AD9858 DDS hardware can be used in addition to a limited number of TTL channels. The TTL lines are mapped to RTIO channels as follows:

+--------------+----------+-----------------+
| RTIO channel | TTL line | Capability      |
+==============+==========+=================+
| 0            | PMT0     | Input only      |
+--------------+----------+-----------------+
| 1            | PMT1     | Input only      |
+--------------+----------+-----------------+
| 2            | TTL0     | Output only     |
+--------------+----------+-----------------+
| 3            | TTL1     | Output only     |
+--------------+----------+-----------------+
| 4            | TTL2     | Output only     |
+--------------+----------+-----------------+
| 5            | TTL3     | Output only     |
+--------------+----------+-----------------+
| 6            | TTL4     | Output only     |
+--------------+----------+-----------------+
| 7            | TTL5     | Output only     |
+--------------+----------+-----------------+
| 8            | FUD      | DDS driver only |
+--------------+----------+-----------------+

The input only limitation on channels 0 and 1 comes from the QC-DAQ adapter. When the adapter is not used (and physically unplugged from the Papilio Pro board), the corresponding pins on the Papilio Pro can be used as outputs. Do not configure these channels as outputs when the adapter is plugged, as this would cause electrical contention.
