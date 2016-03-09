Core device
===========

The core device is a FPGA-based hardware component that contains a softcore CPU tightly coupled with the so-called RTIO core that provides precision timing. The CPU executes Python code that is statically compiled by the ARTIQ compiler, and communicates with the core device peripherals (TTL, DDS, etc.) over the RTIO core. This architecture provides high timing resolution, low latency, low jitter, high level programming capabilities, and good integration with the rest of the Python experiment code.

While it is possible to use all the other parts of ARTIQ (controllers, master, GUI, dataset management, etc.) without a core device, many experiments require it.


.. _core-device-flash-storage:

Flash storage
*************

The core device contains some flash space that can be used to store configuration data.

This storage area is used to store the core device MAC address, IP address and even the idle kernel.

The flash storage area is one sector (typically 64 kB) large and is organized as a list of key-value records.

This flash storage space can be accessed by using ``artiq_coreconfig`` (see: :ref:`core-device-configuration-tool`).

.. _board-ports:

FPGA board ports
****************

KC705
-----

The main target board for the ARTIQ core device is the KC705 development board from Xilinx. It supports the NIST QC1 hardware via an adapter, and the NIST CLOCK and QC2 hardware (FMC).

NIST QC1
++++++++

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

NIST CLOCK
++++++++++

With the CLOCK hardware, the TTL lines are mapped as follows:

+--------------------+-----------------------+--------------+
| RTIO channel       | TTL line              | Capability   |
+====================+=======================+==============+
| 3,7,11,15          | TTL3,7,11,15          | Input+Output |
+--------------------+-----------------------+--------------+
| 0-2,4-6,8-10,12-14 | TTL0-2,4-6,8-10,12-14 | Output       |
+--------------------+-----------------------+--------------+
| 16                 | PMT0                  | Input        |
+--------------------+-----------------------+--------------+
| 17                 | PMT1                  | Input        |
+--------------------+-----------------------+--------------+
| 18                 | SMA_GPIO_N            | Input+Output |
+--------------------+-----------------------+--------------+
| 19                 | LED                   | Output       |
+--------------------+-----------------------+--------------+
| 20                 | AMS101_LDAC_B         | Output       |
+--------------------+-----------------------+--------------+
| 21                 | LA32_P                | Clock        |
+--------------------+-----------------------+--------------+

The board has RTIO SPI buses mapped as follows:

+--------------+-------------+-------------+-----------+------------+
| RTIO channel | CS_N        | MOSI        | MISO      | CLK        |
+==============+=============+=============+===========+============+
| 22           | AMS101_CS_N | AMS101_MOSI |           | AMS101_CLK |
+--------------+-------------+-------------+-----------+------------+
| 23           | SPI0_CS_N   | SPI0_MOSI   | SPI0_MISO | SPI0_CLK   |
+--------------+-------------+-------------+-----------+------------+
| 24           | SPI1_CS_N   | SPI1_MOSI   | SPI1_MISO | SPI1_CLK   |
+--------------+-------------+-------------+-----------+------------+
| 25           | SPI2_CS_N   | SPI2_MOSI   | SPI2_MISO | SPI2_CLK   |
+--------------+-------------+-------------+-----------+------------+

The DDS bus is on channel 26.


NIST QC2
++++++++

With the QC2 hardware, the TTL lines are mapped as follows:

TODO

The QC2 hardware uses TCA6424A I2C I/O expanders to define the directions of its TTL buffers. There is one such expander per FMC card, and they are selected using the PCA9548 on the KC705.

To avoid I/O contention, the startup kernel should first program the TCA6424A expanders and then call ``output()`` on all ``TTLInOut`` channels that should be configured as outputs.

See :mod:`artiq.coredevice.i2c` for more details.


Pipistrello
-----------

The low-cost Pipistrello FPGA board can be used as a lower-cost but slower alternative. Since the device does not have a native network interface, a PPP session is run over the serial port (which is then run over USB). To establish the PPP session with the core device, giving it the IP address 10.0.0.2, as root execute::

    pppd /dev/ttyUSB1 115200 noauth nodetach local nocrtscts novj 10.0.0.1:10.0.0.2

When plugged to an adapter, the NIST QC1 hardware can be used. The TTL lines are mapped to RTIO channels as follows:

+--------------+------------+--------------+
| RTIO channel | TTL line   | Capability   |
+==============+============+==============+
| 0            | PMT0       | Input        |
+--------------+------------+--------------+
| 1            | PMT1       | Input        |
+--------------+------------+--------------+
| 2-16         | TTL0-14    | Output       |
+--------------+------------+--------------+
| 17           | EXT_LED    | Output       |
+--------------+------------+--------------+
| 18           | USER_LED_1 | Output       |
+--------------+------------+--------------+
| 19           | USER_LED_2 | Output       |
+--------------+------------+--------------+
| 20           | USER_LED_3 | Output       |
+--------------+------------+--------------+
| 21           | USER_LED_4 | Output       |
+--------------+------------+--------------+
| 22           | TTL15      | Clock        |
+--------------+------------+--------------+

The input only limitation on channels 0 and 1 comes from the QC-DAQ adapter. When the adapter is not used (and physically unplugged from the Pipistrello board), the corresponding pins on the Pipistrello can be used as outputs. Do not configure these channels as outputs when the adapter is plugged, as this would cause electrical contention.

The board can accept an external RTIO clock connected to PMT2. If the DDS box does not drive the PMT2 pair, use XTRIG and patch the XTRIG transceiver output on the adapter board onto C:15 disconnecting PMT2.

The board has one RTIO SPI bus on the PMOD connector, compliant to PMOD
Interface Type 2 (SPI) and 2A (expanded SPI):

+--------------+--------+--------+--------+--------+
| RTIO channel | CS_N   | MOSI   | MISO   | CLK    |
+==============+========+========+========+========+
| 23           | PMOD_0 | PMOD_1 | PMOD_2 | PMOD_3 |
+--------------+--------+--------+--------+--------+
