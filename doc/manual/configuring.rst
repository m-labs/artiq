Networking and configuration
============================

.. _core-device-networking: 

Setting up the core device IP networking
----------------------------------------

For Kasli, insert a SFP/RJ45 transceiver (normally included with purchases from M-Labs and QUARTIQ) into the SFP0 port and connect it to an Ethernet port in your network. If the port is 10Mbps or 100Mbps and not 1000Mbps, make sure that the SFP/RJ45 transceiver supports the lower rate. Many SFP/RJ45 transceivers only support the 1000Mbps rate. If you do not have a SFP/RJ45 transceiver that supports 10Mbps and 100Mbps rates, you may instead use a gigabit Ethernet switch in the middle to perform rate conversion. 

You can also insert other types of SFP transceivers into Kasli if you wish to use it directly in e.g. an optical fiber Ethernet network. 

Kasli-SoC already directly features RJ45 10/100/1000T Ethernet, but the same is still true of its SFP ports.

If you purchased a Kasli or Kasli-SoC device from M-Labs, it usually comes with the IP address ``192.168.1.75``. Once you can reach this IP, it can be changed by running: ::

  $ artiq_coremgmt -D 192.168.1.75 config write -s ip [new IP]

and then rebooting the device

  $ artiq_coremgmt reboot 

* For Kasli-SoC: 
  
If the ``ip`` config is not set, Kasli-SoC firmware defaults to using the IP address ``192.168.1.56``. It can then be changed with the procedure above. 

* For Kasli or KC705: 

If the ``ip`` config field is not set or set to ``use_dhcp``, the device will attempt to obtain an IP address and default gateway using DHCP. If a static IP address is nonetheless wanted, it can be flashed directly (OpenOCD must be installed and configured, as above), along with, as necessary, default gateway, IPv6, and/or MAC address: ::

  $ artiq_mkfs flash_storage.img [-s mac xx:xx:xx:xx:xx:xx] [-s ip xx.xx.xx.xx/xx] [-s ipv4_default_route xx.xx.xx.xx] [-s ip6 xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx/xx] [-s ipv6_default_route xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx]
  $ artiq_flash -t [board] -V [variant] -f flash_storage.img storage start

On Kasli or Kasli SoC devices, specifying the MAC address is unnecessary, as they can obtain it from their EEPROM. If you only want to access the core device from the same subnet, default gateway and IPv4 prefix length may also be ommitted. Regardless of board, once a device is reachable by ``artiq_coremgmt``, any of these fields can be accessed using ``artiq_coremgmt config write`` and ``artiq_coremgt config read``; see also :ref:`Utilities <core-device-management-tool>`.     

If DHCP has been used the address can be found in the console output, which can be viewed using: ::

  $ python -m misoc.tools.flterm /dev/ttyUSB2

Check that you can ping the device. If ping fails, check that the Ethernet link LED is ON - on Kasli, it is the LED next to the SFP0 connector. As a next step, look at the messages emitted on the UART during boot. Use a program such as flterm or PuTTY to connect to the device's serial port at 115200bps 8-N-1 and reboot the device. On Kasli, the serial port is on FTDI channel 2 with v1.1 hardware (with channel 0 being JTAG) and on FTDI channel 1 with v1.0 hardware. Note that on Windows you might need to install the `FTDI drivers <https://ftdichip.com/drivers/>`_ first.

Regarding use of IPv6, note that the device also has a link-local address that corresponds to its EUI-64, which can be used simultaneously to the IPv6 address defined by using the ``ip6`` configuration key, which may be of arbitrary nature. 

.. _miscellaneous_config_core_device: 

Miscellaneous configuration of the core device
----------------------------------------------

These steps are optional, and only need to be executed if necessary for your specific purposes. In all cases, the core device generally needs to be restarted for changes to take effect.

Flash idle or startup kernel
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The idle kernel is the kernel (that is, a piece of code running on the core device; see :ref:`next topic <connecting-to-the-core-device>` for more information about kernels) which the core device runs whenever it is not connected to the host via Ethernet. This kernel is therefore stored immediately in the :ref:`core device configuration flash storage <core-device-flash-storage>`.

To flash the idle kernel, first compile an idle experiment. Since the core device is not connected to the host, RPCs (calling Python code running on the host from the kernel) are forbidden, and its ``run()`` method must be a kernel, marked correctly with the ``@kernel`` decorator. Write the compiled experiment to the core device configuration flash storage, under the key ``idle_kernel``: ::

  $ artiq_compile idle.py
  $ artiq_coremgmt config write -f idle_kernel idle.elf

The startup kernel is the kernel executed once immediately whenever the core device powers on. Uses include initializing DDSes, setting TTL directions etc. Proceed as with the idle kernel, but using the ``startup_kernel`` key in the ``artiq_coremgmt`` command. 

For DRTIO systems, the startup kernel should wait until the desired destinations (including local RTIO) are up, using :meth:`artiq.coredevice.Core.get_rtio_destination_status`.

Select the RTIO clock source
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The core device may use any of: an external clock signal, its internal clock with external frequency reference, or its internal clock with internal crystal reference. Clock source and timing are set at power-up. To find out what clock signal you are using, check startup logs with ``artiq_coremgmt log``. 

The default is to use an internal 125MHz clock. To select a source, use a command of the form: ::

  $ artiq_coremgmt config write -s rtio_clock int_125  # internal 125MHz clock (default)
  $ artiq_coremgmt config write -s rtio_clock ext0_synth0_10to125  # external 10MHz reference used to synthesize internal 125MHz

See :ref:`core-device-clocking` for availability of specific options.    

Set up resolving RTIO channels to their names
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This feature allows you to print the channels' respective names alongside with their numbers in RTIO error messages. To enable it, run the ``artiq_rtiomap`` tool and write its result into the device config at the ``device_map`` key: ::

  $ artiq_rtiomap dev_map.bin
  $ artiq_coremgmt config write -f device_map dev_map.bin

.. note:: More information on the ``artiq_rtiomap`` utility can be found on the :ref:`Utilities <rtiomap-tool>` page.

Enabling event spreading 
------------------------

This feature changes the logic used for queueing RTIO output events in the core device for a more efficient use of FPGA resources, at the cost of introducing nondeterminism and potential unpredictability in certain timing errors (specifically gateware :ref:`sequence errors<sequence-errors>`). It can be enabled with the config key ``sed_spread_enable``. See :ref:`sed-event-spreading`.

Load the DRTIO routing table
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you are using DRTIO and the default routing table (for a star topology) is not suitable to your needs, you will first need to prepare and load a different routing table. See :ref:`Using DRTIO <drtio-routing>`.


