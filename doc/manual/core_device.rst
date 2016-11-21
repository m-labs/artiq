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

All boards have a serial interface running at 115200bps 8-N-1 that can be used for debugging.

KC705
-----

The main target board for the ARTIQ core device is the KC705 development board from Xilinx. It supports the NIST CLOCK and QC2 hardware (FMC).

Common problems
+++++++++++++++

* The SW13 switches on the board need to be set to 00001.
* When connected, CLOCK adapter breaks the JTAG chain due to TDI not being connect to TDO on the FMC mezzanine.
* On some boards, the JTAG USB connector is not correctly soldered.

VADJ
++++

With the NIST CLOCK and QC2 adapters, for safe operation of the DDS buses (to prevent damage to the IO banks of the FPGA), the FMC VADJ rail of the KC705 should be changed to 3.3V. Plug the Texas Instruments USB-TO-GPIO PMBus adapter into the PMBus connector in the corner of the KC705 and use the Fusion Digital Power Designer software to configure (requires Windows). Write to chip number U55 (address 52), channel 4, which is the VADJ rail, to make it 3.3V instead of 2.5V.  Power cycle the KC705 board to check that the startup voltage on the VADJ rail is now 3.3V.


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

+--------------------+-----------------------+--------------+
| RTIO channel       | TTL line              | Capability   |
+====================+=======================+==============+
| 0-39               | TTL0-39               | Input+Output |
+--------------------+-----------------------+--------------+
| 40                 | SMA_GPIO_N            | Input+Output |
+--------------------+-----------------------+--------------+
| 41                 | LED                   | Output       |
+--------------------+-----------------------+--------------+
| 42                 | AMS101_LDAC_B         | Output       |
+--------------------+-----------------------+--------------+
| 43, 44             | CLK0, CLK1            | Clock        |
+--------------------+-----------------------+--------------+

The board has RTIO SPI buses mapped as follows:

+--------------+-------------+-------------+-----------+------------+
| RTIO channel | CS_N        | MOSI        | MISO      | CLK        |
+==============+=============+=============+===========+============+
| 45           | AMS101_CS_N | AMS101_MOSI |           | AMS101_CLK |
+--------------+-------------+-------------+-----------+------------+
| 46           | SPI0_CS_N   | SPI0_MOSI   | SPI0_MISO | SPI0_CLK   |
+--------------+-------------+-------------+-----------+------------+
| 47           | SPI1_CS_N   | SPI1_MOSI   | SPI1_MISO | SPI1_CLK   |
+--------------+-------------+-------------+-----------+------------+
| 48           | SPI2_CS_N   | SPI2_MOSI   | SPI2_MISO | SPI2_CLK   |
+--------------+-------------+-------------+-----------+------------+
| 49           | SPI3_CS_N   | SPI3_MOSI   | SPI3_MISO | SPI3_CLK   |
+--------------+-------------+-------------+-----------+------------+

There are two DDS buses on channels 50 (LPC, DDS0-DDS11) and 51 (HPC, DDS12-DDS23).


The QC2 hardware uses TCA6424A I2C I/O expanders to define the directions of its TTL buffers. There is one such expander per FMC card, and they are selected using the PCA9548 on the KC705.

To avoid I/O contention, the startup kernel should first program the TCA6424A expanders and then call ``output()`` on all ``TTLInOut`` channels that should be configured as outputs.

See :mod:`artiq.coredevice.i2c` for more details.


Phaser
++++++

The Phaser adapter is an AD9154-FMC-EBZ, a 4 channel 2.4 GHz DAC on an FMC HPC card.

+--------------+------------+--------------+
| RTIO channel | TTL line   | Capability   |
+==============+============+==============+
| 0            | SMA_GPIO_N | Input+Output |
+--------------+------------+--------------+
| 1            | LED        | Output       |
+--------------+------------+--------------+
| 2            | SYSREF     | Input        |
+--------------+------------+--------------+
| 3            | SYNC       | Input        |
+--------------+------------+--------------+

The SAWG channels start with RTIO channel number 4, each occupying 3 channels.

The board has one non-RTIO SPI bus that is accessible through
:mod:`artiq.coredevice.ad9154`.


Pipistrello
-----------

The low-cost Pipistrello FPGA board can be used as a lower-cost but slower alternative. Since the device does not have a native network interface, a PPP session is run over the serial port (which is then run over USB). To establish the PPP session with the core device, giving it the IP address 10.0.0.2, as root execute::

    pppd /dev/ttyUSB1 115200 noauth nodetach local nocrtscts novj 10.0.0.1:10.0.0.2

.. warning:: Windows is not supported.

.. warning:: The Pipistrello draws a high current over USB, and that current increases when the FPGA design is active. If you experience problems such as intermittent board freezes or USB errors, try connecting it to a self-powered USB hub.

The TTL lines are mapped to RTIO channels as follows:

+--------------+------------+--------------+
| RTIO channel | TTL line   | Capability   |
+==============+============+==============+
| 0-1          | B0-1       | Input+Output |
+--------------+------------+--------------+
| 2-14         | B2-14      | Output       |
+--------------+------------+--------------+
| 15           | USER_LED_1 | Output       |
+--------------+------------+--------------+
| 16           | USER_LED_2 | Output       |
+--------------+------------+--------------+
| 17           | USER_LED_3 | Output       |
+--------------+------------+--------------+
| 18           | USER_LED_4 | Output       |
+--------------+------------+--------------+
| 19           | B15        | Clock        |
+--------------+------------+--------------+

The board can accept an external RTIO clock connected to C15.

The board has one RTIO SPI bus on the PMOD connector, compliant to PMOD
Interface Type 2 (SPI) and 2A (expanded SPI):

+--------------+--------+--------+--------+--------+
| RTIO channel | CS_N   | MOSI   | MISO   | CLK    |
+==============+========+========+========+========+
| 16           | PMOD_0 | PMOD_1 | PMOD_2 | PMOD_3 |
+--------------+--------+--------+--------+--------+
