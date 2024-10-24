Core device
===========

The core device is a FPGA-based hardware component that contains a softcore or hardcore CPU tightly coupled with the so-called RTIO core, which runs in gateware and provides precision timing. The CPU executes Python code that is statically compiled by the ARTIQ compiler and communicates with peripherals (TTL, DDS, etc.) through the RTIO core, as described in :doc:`rtio`. This architecture provides high timing resolution, low latency, low jitter, high-level programming capabilities, and good integration with the rest of the Python experiment code.

While it is possible to use the other parts of ARTIQ (controllers, master, GUI, dataset management, etc.) without a core device, most use cases will require it.

.. _configuration-storage:

Configuration storage
---------------------

The core device reserves some storage space (either flash or directly on SD card, depending on target board) to store configuration data. The configuration data is organized as a list of key-value records, accessible either through :mod:`~artiq.frontend.artiq_mkfs` and :mod:`~artiq.frontend.artiq_flash` or, preferably in most cases, the ``config`` option of the :mod:`~artiq.frontend.artiq_coremgmt` core management tool (see below). Information can be stored to keys of any name, but the specific keys currently used and referenced by ARTIQ are summarized below:

``idle_kernel``
  Stores (compiled ``.tar`` or ``.elf`` binary of) idle kernel. See :ref:`core-device-config`.
``startup_kernel``
  Stores (compiled ``.tar`` or ``.elf`` binary of) startup kernel. See :ref:`core-device-config`.
``ip``
  Sets IP address of core device. For this and other networking options see also :ref:`core-device-networking`.
``mac``
  Sets MAC address of core device. Unnecessary on Kasli or Kasli-SoC, which can obtain it from EEPROM.
``ipv4_default_route``
  Sets IPv4 default route.
``ip6``
  Sets IPv6 address of core device. Can be set irrespective of and used simultaneously as IPv4 address above.
``ipv6_default_route``
  Sets IPv6 default route.
``sed_spread_enable``
  If set to ``1``, will activate :ref:`sed-event-spreading` in this core device. Needs to be set separately for satellite devices in a DRTIO setting.
``log_level``
  Sets core device log level. Possible levels are ``TRACE``, ``DEBUG``, ``INFO``, ``WARN``, ``ERROR``, and ``OFF``. Note that enabling higher log levels will produce some core device slowdown.
``uart_log_level``
  Sets UART log level, with same options. Printing a large number of messages to UART log will produce a significant slowdown.
``rtio_clock``
  Sets the RTIO clock; see :ref:`core-device-clocking`.
``routing_table``
  Sets the routing table in DRTIO systems; see :ref:`drtio-routing`. If not set, a star topology is assumed.
``device_map``
  If set, allows the core log to connect RTIO channels to device names and use device names as well as channel numbers in log output. A correctly formatted table can be automatically generated with :mod:`~artiq.frontend.artiq_rtiomap`, see :ref:`Utilities<rtiomap-tool>`.
``net_trace``
  If set to ``1``, will activate net trace (print all packets sent and received to UART and core log). This will considerably slow down all network response from the core. Not applicable for ARTIQ-Zynq (see :ref:`Zynq devices <devices-table>`).
``panic_reset``
  If set to ``1``, core device will restart automatically.  Not applicable for ARTIQ-Zynq.
``no_flash_boot``
  If set to ``1``, will disable flash boot. Network boot is attempted if possible. Not applicable for ARTIQ-Zynq.
``boot``
  Allows full firmware/gateware (``boot.bin``) to be written with :mod:`~artiq.frontend.artiq_coremgmt`, on ARTIQ-Zynq systems only.

Common configuration commands
-----------------------------

To write, then read, the value ``test_value`` in the key ``my_key``::

    $ artiq_coremgmt config write -s my_key test_value
    $ artiq_coremgmt config read my_key
    b'test_value'

You do not need to remove a record in order to change its value. Just overwrite it::

    $ artiq_coremgmt config write -s my_key some_value
    $ artiq_coremgmt config write -s my_key some_other_value
    $ artiq_coremgmt config read my_key
    b'some_other_value'

You can write several records at once::

    $ artiq_coremgmt config write -s key1 value1 -f key2 filename -s key3 value3

You can also write entire files in a record using the ``-f`` option. This is useful for instance to write the startup and idle kernels into the flash storage::

    $ artiq_coremgmt config write -f idle_kernel idle.elf
    $ artiq_coremgmt config read idle_kernel | head -c9
    b'\x7fELF

The same option is used to write ``boot.bin`` in ARTIQ-Zynq. Note that the ``boot`` key is write-only.

See also the full reference of :mod:`~artiq.frontend.artiq_coremgmt` in :ref:`Utilities <core-device-management-tool>`.

.. _core-device-clocking:

Clocking
--------

The core device generates the RTIO clock using a PLL locked either to an internal crystal or to an external frequency reference. If choosing the latter, external reference must be provided (via front panel SMA input on Kasli boards). Valid configuration options include:

  * ``int_100`` - internal crystal reference is used to synthesize a 100MHz RTIO clock,
  * ``int_125`` - internal crystal reference is used to synthesize a 125MHz RTIO clock (default option),
  * ``int_150`` - internal crystal reference is used to synthesize a 150MHz RTIO clock.
  * ``ext0_synth0_10to125`` - external 10MHz reference clock used to synthesize a 125MHz RTIO clock,
  * ``ext0_synth0_80to125`` - external 80MHz reference clock used to synthesize a 125MHz RTIO clock,
  * ``ext0_synth0_100to125`` - external 100MHz reference clock used to synthesize a 125MHz RTIO clock,
  * ``ext0_synth0_125to125`` - external 125MHz reference clock used to synthesize a 125MHz RTIO clock.

The selected option can be observed in the core device boot logs and accessed using ``artiq_coremgmt config`` with key ``rtio_clock``.

As of ARTIQ 8, it is now possible for Kasli and Kasli-SoC configurations to enable WRPLL -- a clock recovery method using `DDMTD <http://white-rabbit.web.cern.ch/documents/DDMTD_for_Sub-ns_Synchronization.pdf>`_ and Si549 oscillators -- both to lock the main RTIO clock and (in DRTIO configurations) to lock satellites to master. This is set by the ``enable_wrpll`` option in the :ref:`JSON description file <system-description>`. Because WRPLL requires slightly different gateware and firmware, it is necessary to re-flash devices to enable or disable it in extant systems. If you would like to obtain the firmware for a different WRPLL setting through AFWS, write to the helpdesk@ email.

If phase noise performance is the priority, it is recommended to use ``ext0_synth0_125to125`` over other ``ext0`` options, as this bypasses the (noisy) MMCM.

If not using WRPLL, PLL can also be bypassed entirely with the options

    * ``ext0_bypass`` (input clock used directly)
    * ``ext0_bypass_125`` (explicit alias)
    * ``ext0_bypass_100`` (explicit alias)

Bypassing the PLL ensures the skews between input clock, downstream clock outputs, and RTIO clock are deterministic across reboots of the system. This is useful when phase determinism is required in situations where the reference clock fans out to other devices before reaching the master.

.. _types-of-boards:

Types of boards
---------------

To clarify the terminology used in ARTIQ, we can distinguish the boards into a few key groups. There are two primary ways to categorize them. The first is based on the ARTIQ platform itself: either ARTIQ or ARTIQ-Zynq. ARTIQ-Zynq boards specifically refer to those that feature a Xilinx Zynq FPGA. The second distinction is based on how the boards are configured: some use a :ref:`JSON system description file <system-description>`, while others do not.

Below are the current groups of boards:

.. _devices-table:

+------------------------------+------------------------------+
| **Device Type**              | **Devices**                  |
+==============================+==============================+
| Zynq devices                 | Kasli-SoC, ZC706, EBAZ4205   |
+------------------------------+------------------------------+
| JSON variant devices         | Kasli, Kasli-SoC             |
+------------------------------+------------------------------+
| Hardcoded variant devices    | KC705, ZC706, EBAZ4205       |
+------------------------------+------------------------------+

Board details
-------------

FPGA board ports
^^^^^^^^^^^^^^^^

All boards have a serial interface running at 115200bps 8-N-1 that can be used for debugging.

Kasli and Kasli-SoC
^^^^^^^^^^^^^^^^^^^

`Kasli <https://github.com/sinara-hw/Kasli/wiki>`_ and `Kasli-SoC <https://github.com/sinara-hw/Kasli-SOC/wiki>`_ are versatile core devices designed for ARTIQ as part of the open-source `Sinara <https://github.com/sinara-hw/meta/wiki>`_ family of boards. All support interfacing to various EEM daughterboards (TTL, DDS, ADC, DAC...) through twelve onboard EEM ports. Kasli is based on a Xilinx Artix-7 FPGA, and Kasli-SoC, which runs on a separate `Zynq port <https://git.m-labs.hk/M-Labs/artiq-zynq>`_ of the ARTIQ firmware, is based on a Zynq-7000 SoC, notably including an ARM CPU allowing for much heavier software computations at high speeds. They are architecturally very different but supply similar feature sets. Kasli itself exists in two versions, of which the improved Kasli v2.0 is now in more common use, but the original v1.0 remains supported by ARTIQ.

Kasli can be connected to the network using a 1000Base-X SFP module, installed into the SFP0 cage. Kasli-SoC features a built-in Ethernet port to use instead. If configured as a DRTIO satellite, both boards instead reserve SFP0 for the upstream DRTIO connection; remaining SFP cages are available for downstream connections. Equally, if used as a DRTIO master, all free SFP cages are available for downstream connections (i.e. all but SFP0 on Kasli, all four on Kasli-SoC).

The DRTIO line rate depends upon the RTIO clock frequency running, e.g., at 125MHz the line rate is 2.5Gbps, at 150MHz 3.0Gbps, etc. See below for information on RTIO clocks.

KC705 and ZC706
^^^^^^^^^^^^^^^

Two high-end evaluation kits are also supported as alternative ARTIQ core device target boards, respectively the Kintex7 `KC705 <https://www.xilinx.com/products/boards-and-kits/ek-k7-kc705-g.html>`_ and Zynq-SoC `ZC706 <https://www.xilinx.com/products/boards-and-kits/ek-z7-zc706-g.html>`_, both from Xilinx. ZC706, like Kasli-SoC, runs on the ARTIQ-Zynq port. Both are supported in several set variants, namely NIST CLOCK and QC2 (FMC), either available in master, satellite, or standalone variants. See also :doc:`building_developing` for more on system variants.

Common KC705 problems
"""""""""""""""""""""

* The SW13 switches on the board need to be set to 00001.
* When connected, the CLOCK adapter breaks the JTAG chain due to TDI not being connected to TDO on the FMC mezzanine.
* On some boards, the JTAG USB connector is not correctly soldered.

VADJ
""""

With the NIST CLOCK and QC2 adapters, for safe operation of the DDS buses (to prevent damage to the IO banks of the FPGA), the FMC VADJ rail of the KC705 should be changed to 3.3V. Plug the Texas Instruments USB-TO-GPIO PMBus adapter into the PMBus connector in the corner of the KC705 and use the Fusion Digital Power Designer software to configure (requires Windows). Write to chip number U55 (address 52), channel 4, which is the VADJ rail, to make it 3.3V instead of 2.5V.  Power cycle the KC705 board to check that the startup voltage on the VADJ rail is now 3.3V.

EBAZ4205
^^^^^^^^

The `EBAZ4205 <https://github.com/xjtuecho/EBAZ4205>`_ Zynq-SoC control card, originally used in the Ebit E9+ BTC miner, is a low-cost development board (around $20-$30 USD), making it an ideal option for experimenting with ARTIQ. To use the EBAZ4205, it's important to carefully follow the board documentation to configure it to boot from the SD card, as network booting via ``artiq_netboot`` is currently unsupported. This is because the Ethernet PHY is routed through the EMIO, requiring the FPGA to be programmed before the board can establish a network connection.

One useful application of the EBAZ4205 is controlling external devices like the AD9834 DDS Module from ZonRi Technology Co., Ltd. To establish communication between the EBAZ4205 and the AD9834 module, proper configuration of the SPI interface pins is essential. The board's flexibility allows for straightforward control of the DDS once the correct pinout is known. The table below details the necessary connections between the EBAZ4205 and the AD9834 module, including power, ground, and SPI signals.

+--------------------------+---------------------+----------------------------+
| Pin on AD9834 Module     | Chip Function       | Connection on EBAZ4205     |
+==========================+=====================+============================+
| SCLK                     | SCLK                | CLK: DATA3-19 (Pin V20)    |
+--------------------------+---------------------+----------------------------+
| DATA                     | SDATA               | MOSI: DATA3-17 (Pin U20)   |
+--------------------------+---------------------+----------------------------+
| SYNC                     | FSYNC               | CS_N: DATA3-15 (Pin P19)   |
+--------------------------+---------------------+----------------------------+
| FSE (Tied to GND)        | FSELECT             | N/A: Bit Controlled        |
+--------------------------+---------------------+----------------------------+
| PSE (Tied to GND)        | PSELECT             | N/A: Bit Controlled        |
+--------------------------+---------------------+----------------------------+
| GND                      | Ground              | GND: J8-1, J8-3            |
+--------------------------+---------------------+----------------------------+
| VIN                      | AVDD/DVDD           | 3.3V: J8-2                 |
+--------------------------+---------------------+----------------------------+
| RESET (Unused)           | RESET               | N/A: Bit Controlled        |
+--------------------------+---------------------+----------------------------+

For a step-by-step guide, see the `EBAZ4205 and AD9834 setup guide <https://newell.github.io/projects/ebaz4205>`_.

Variant details
---------------

NIST CLOCK
^^^^^^^^^^

With the KC705 CLOCK hardware, the TTL lines are mapped as follows:

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

The DDS bus is on channel 27.

The ZC706 variant is identical except for the following differences:

    - The SMA GPIO on channel 18 is replaced by an Input+Output capable PMOD1_0 line.
    - Since there is no SDIO on the programmable logic side, channel 26 is instead occupied by an additional SPI:

+--------------+------------------+--------------+--------------+--------------+
| RTIO channel | CS_N             | MOSI         | MISO         | CLK          |
+==============+==================+==============+==============+==============+
| 26           | PMOD_SPI_CS_N    | PMOD_SPI_MOSI| PMOD_SPI_MISO| PMOD_SPI_CLK |
+--------------+------------------+--------------+--------------+--------------+

NIST QC2
^^^^^^^^

With the KC705 QC2 hardware, the TTL lines are mapped as follows:

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

To avoid I/O contention, the startup kernel should first program the TCA6424A expanders and then call ``output()`` on all ``TTLInOut`` channels that should be configured as outputs. See :mod:`artiq.coredevice.i2c` for more details.

The ZC706 is identical except for the following differences:

    - The SMA GPIO is once again replaced with PMOD1_0.
    - The first four TTLs also have edge counters, on channels 52, 53, 54, and 55.
