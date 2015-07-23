FPGA board ports
================

KC705
-----

The main target board for the ARTIQ core device is the KC705 development board from Xilinx.

Pipistrello
-----------

The low-cost Pipistrello FPGA board can be used as a lower-cost but slower alternative.

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
| 17           | TTL15    | Clock      |
+--------------+----------+------------+
| 18           | EXT_LED  | Output     |
+--------------+----------+------------+
| 19           | USER_LED | Output     |
+--------------+----------+------------+
| 20           | DDS      | Output     |
+--------------+----------+------------+

The input only limitation on channels 0 and 1 comes from the QC-DAQ adapter. When the adapter is not used (and physically unplugged from the Pipistrello board), the corresponding pins on the Pipistrello can be used as outputs. Do not configure these channels as outputs when the adapter is plugged, as this would cause electrical contention.

The board can accept an external RTIO clock connected to PMT2. If the DDS box
does not drive the PMT2 pair, use XTRIG and patch the XTRIG transciever output
on the adapter board onto C:15 disconnecting PMT2.
