FPGA board ports
================

KC705
-----

The main target board for the ARTIQ core device is the KC705 development board from Xilinx.

Papilio Pro
-----------

The low-cost Papilio Pro FPGA board can be used with some limitations.

When plugged to a QC-DAQ LVDS adapter, the AD9858 DDS hardware can be used in addition to a limited number of TTL channels. The TTL lines are mapped to RTIO channels as follows:

+--------------+----------+----------------+
| RTIO channel | TTL line | Capability     |
+==============+==========+================+
| 0            | PMT0     | Output + input |
+--------------+----------+----------------+
| 1            | TTL0     | Output only    |
+--------------+----------+----------------+
| 2            | TTL1     | Output only    |
+--------------+----------+----------------+
| 3            | TTL2     | Output only    |
+--------------+----------+----------------+
