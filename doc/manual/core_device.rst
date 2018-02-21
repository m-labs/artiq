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
* When connected, the CLOCK adapter breaks the JTAG chain due to TDI not being connected to TDO on the FMC mezzanine.
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
| 27                 | FMCDIO_DIRCTL_CLK     | Output       |
+--------------------+-----------------------+--------------+
| 28                 | FMCDIO_DIRCTL_SER     | Output       |
+--------------------+-----------------------+--------------+
| 29                 | FMCDIO_DIRCTL_LATCH   | Output       |
+--------------------+-----------------------+--------------+
| 31                 | ZOTINO_LDAC           | Output       |
+--------------------+-----------------------+--------------+
| 33                 | URUKUL_IO_UPDATE      | Output       |
+--------------------+-----------------------+--------------+
| 34                 | URUKUL_DDS_RESET      | Output       |
+--------------------+-----------------------+--------------+
| 35                 | URUKUL_SW0            | Output       |
+--------------------+-----------------------+--------------+
| 36                 | URUKUL_SW1            | Output       |
+--------------------+-----------------------+--------------+
| 37                 | URUKUL_SW2            | Output       |
+--------------------+-----------------------+--------------+
| 38                 | URUKUL_SW3            | Output       |
+--------------------+-----------------------+--------------+

The board has RTIO SPI buses mapped as follows:

+--------------+------------------+--------------+--------------+------------+
| RTIO channel | CS_N             | MOSI         | MISO         | CLK        |
+==============+==================+==============+==============+============+
| 22           | AMS101_CS_N      | AMS101_MOSI  |              | AMS101_CLK |
+--------------+------------------+--------------+--------------+------------+
| 23           | SPI0_CS_N        | SPI0_MOSI    | SPI0_MISO    | SPI0_CLK   |
+--------------+------------------+--------------+--------------+------------+
| 24           | SPI1_CS_N        | SPI1_MOSI    | SPI1_MISO    | SPI1_CLK   |
+--------------+------------------+--------------+--------------+------------+
| 25           | SPI2_CS_N        | SPI2_MOSI    | SPI2_MISO    | SPI2_CLK   |
+--------------+------------------+--------------+--------------+------------+
| 26           | MMC_SPI_CS_N     | MMC_SPI_MOSI | MMC_SPI_MISO | MMC_SPI_CLK|
+--------------+------------------+--------------+--------------+------------+
| 30           | ZOTINO_CS_N      | ZOTINO_MOSI  | ZOTINO_MISO  | ZOTINO_CLK |
+--------------+------------------+--------------+--------------+------------+
| 32           | URUKUL_CS_N[0:2] | URUKUL_MOSI  | URUKUL_MISO  | URUKUL_CLK |
+--------------+------------------+--------------+--------------+------------+

The DDS bus is on channel 39.

This configuration supports a Zotino and/or an Urukul connected to the KC705 FMC HPC through a FMC DIO 32ch LVDS v1.2 and a VHDCI breakout board rev 1.0 or rev 1.1. On the VHDCI breakout board, the VHDCI cable to the KC705 should be plugged into to the bottom connector. The EEM cable to the Zotino should be connected to J41 and the EEM cables to Urukul to J42 and J43.

The shift registers on the FMC card should be configured to set the directions of its LVDS buffers, using :mod:`artiq.coredevice.shiftreg`.

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

Kasli
-----

`Kasli <https://github.com/m-labs/sinara/wiki/Kasli>`_ is a versatile core device designed for ARTIQ as part of the `Sinara <https://github.com/m-labs/sinara/wiki>`_ family of boards.

Opticlock
+++++++++

In the opticlock variant, Kasli is the core device controlling three `DIO_BNC <https://github.com/m-labs/sinara/wiki/DIO_BNC>`_ boards, one `Urukul-AD9912 <https://github.com/m-labs/sinara/wiki/Urukul>`_, one `Urukul-AD9910 <https://github.com/m-labs/sinara/wiki/Urukul>`_, and one Sampler `<https://github.com/m-labs/sinara/wiki/Sampler>`_.

Kasli is connected to the network using a 1000Base-X SFP module. `No-name
<fs.com>`_ BiDi (1000Base-BX) modules have been used successfully. The SFP module for the network
should be installed into the SFP0 cage.

Kasli is supplied with 100 MHz reference at its SMA input.
Both Urukul boards are supplied with a 100 MHz reference clock on their external
SMA inputs.

The RTIO clock frequency is 125 MHz, which is synthesized from the 100 MHz reference using the Si5324.

The first four TTL channels are used as inputs. The rest are outputs.

DRTIO master
++++++++++++

Kasli can be used as a DRTIO master that provides local RTIO channels and can additionally control one DRTIO satellite.

The RTIO clock frequency is 150 MHz, which is synthesized from the Si5324 crystal. The DRTIO line rate is 3 Gbps.

The SFP module for the Ethernet network should be installed into the SFP0 cage, and the DRTIO connection is on SFP2.

DRTIO satellite
+++++++++++++++

Kasli can be used as a DRTIO satellite with a 150 MHz RTIO clock and a 3 Gbps DRTIO line rate.

The DRTIO connection is on SFP0.
