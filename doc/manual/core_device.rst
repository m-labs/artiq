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

+--------------+--------------+--------------+--------------+------------+
| RTIO channel | CS_N         | MOSI         | MISO         | CLK        |
+==============+==============+==============+==============+============+
| 22           | AMS101_CS_N  | AMS101_MOSI  |              | AMS101_CLK |
+--------------+--------------+--------------+--------------+------------+
| 23           | SPI0_CS_N    | SPI0_MOSI    | SPI0_MISO    | SPI0_CLK   |
+--------------+--------------+--------------+--------------+------------+
| 24           | SPI1_CS_N    | SPI1_MOSI    | SPI1_MISO    | SPI1_CLK   |
+--------------+--------------+--------------+--------------+------------+
| 25           | SPI2_CS_N    | SPI2_MOSI    | SPI2_MISO    | SPI2_CLK   |
+--------------+--------------+--------------+--------------+------------+
| 26           | MMC_SPI_CS_N | MMC_SPI_MOSI | MMC_SPI_MISO | MMC_SPI_CLK|
+--------------+--------------+--------------+--------------+------------+

The DDS bus is on channel 27.


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


.. _phaser:

Phaser
++++++

The Phaser adapter is an AD9154-FMC-EBZ, a 4 channel 2.4 GHz DAC on an FMC HPC card.

Phaser is a proof-of-concept design of a GHz-datarate, multi-channel, interpolating, multi-tone, direct digital synthesizer (DDS) compatible with ARTIQ's RTIO channels.
Ultimately it will be the basis for the ARTIQ Sayma Smart Arbitrary Waveform Generator project. See https://github.com/m-labs/sinara.

*Features*:

* up to 4 channels
* up to 500 MHz data rate per channel (KC705 limitation)
* up to 8x interpolation to 2.4 GHz DAC sample rate
* Real-time sample-coherent control over amplitude, frequency, phase of each channel through ARTIQ RTIO commands
* Full configurability of the AD9154 and AD9516 through SPI with ARTIQ kernel support
* All SPI registers and register bits exposed as human readable names
* Parametrized JESD204B core (also capable of operation with eight lanes)
* The code can be reconfigured. Possible example configurations are: support 2 channels at 1 GHz datarate, support 4 channels at 300 MHz data rate, no interpolation, and using mix mode to stress the second and third Nyquist zones (150-300 MHz and 300-450 MHz). Please contact M-Labs if you need help with this.

The hardware required is a KC705 with an AD9154-FMC-EBZ plugged into the HPC connector and a low-noise sample rate reference clock.

This work was supported by the Army Research Lab and the University of Maryland.

Installation
............

These installation instructions are a short form of those in the ARTIQ manual.
* See the chapter on setting up a :ref:`development environment <develop-from-conda>`.
* When compiling the binaries, use the ``phaser`` target:::
  $ python -m artiq.gateware.targets.kc705_phaser
* From time to time and on request there may be pre-built binaries in the
  ``artiq-kc705-phaser`` package on the M-Labs conda package label.

Setup
.....

* Setup the KC705 (jumpers, etc.) observing the ARTIQ manual. VADJ does not need to be changed.
* On the AD9154-FMC-EBZ put jumpers:

  - on XP1, between pin 5 and 6 (will keep the PIC in reset)
  - on JP3 (will force output enable on FXLA108)

* Refer to the ARTIQ documentation to configure the MAC and IP addresses and other settings. If the board was running stock ARTIQ before, the settings will be kept.
* A 300 MHz clock of roughly 10 dBm (0.2 to 3.4 V peak-to-peak into 50 Ohm) must be connected to the AD9154-FMC-EBZ J1. The input is 50 Ohm terminated. The RTIO clock, DAC deviceclock, FPGA deviceclock, and SYSREF are derived from this signal.
* The RTIO coarse clock (the rate of the RTIO timestamp counter) is 150 MHz. The RTIO ``ref_period`` is 1/150 MHz = 5ns/6. The RTIO ``ref_multiplier`` is ``8``. C.f. ``device_db.py`` for both variables. The JED204B DAC data rate and DAC device clock are both 300 MHz. The JESD204B line rate is 6 GHz.
* Configure an oscilloscope to trigger at 0.5 V on rising edge of ttl_sma (user_gpio_n on the KC705 board). Monitor DAC0 (J17) on the oscilloscope set for 100 mV/div and 200 ns/div.
* An example device database, several status and test scripts are provided in ``artiq/examples/phaser/``. ::

    cd artiq/examples/phaser

* Edit ``device_db.py`` to match the hostname or IP address of the core device.
* Use ``ping`` and ``flterm`` to verify that the core device starts up and boots correctly.

Usage
.....

* Run ``artiq_run repository/demo.py`` for an example that exercises several different use cases of synchronized phase, amplitude, and frequency updates.
  for an example that exercises several different use cases of synchronized phase, amplitude, and frequency updates.
* Run ``artiq_run repository/demo_2tone.py`` for an example that emits a shaped two-tone pulse.
* Implement your own experiments using the SAWG channels.
* Verify clock stability between the sample rate reference clock and the DAC outputs.

RTIO channels
.............

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

The SAWG channels start with RTIO channel number 3, each SAWG channel occupying 10 RTIO channels.

The board has one non-RTIO SPI bus that is accessible through
:mod:`artiq.coredevice.ad9154`.
