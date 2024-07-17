Networking and configuration
============================

Setting up core device networking
---------------------------------

For Kasli, insert a SFP/RJ45 transceiver (normally included with purchases from M-Labs and QUARTIQ) into the SFP0 port and connect it to an Ethernet port in your network. If the port is 10Mbps or 100Mbps and not 1000Mbps, make sure that the SFP/RJ45 transceiver supports the lower rate. Many SFP/RJ45 transceivers only support the 1000Mbps rate. If you do not have a SFP/RJ45 transceiver that supports 10Mbps and 100Mbps rates, you may instead use a gigabit Ethernet switch in the middle to perform rate conversion. 

You can also insert other types of SFP transceivers into Kasli if you wish to use it directly in e.g. an optical fiber Ethernet network. Kasli-SoC already directly features RJ45 10/100/1000 Ethernet.

If you purchased a Kasli or Kasli-SoC device from M-Labs, it will arrive with an IP address already set, normally the one requested in the web shop at time of purchase. Otherwise, if you chose not to make a request, the default IP M-Labs uses is ``192.168.1.75``. Once you can reach your core device, the IP can be changed at any time by running: ::

  $ artiq_coremgmt -D [old IP] config write -s ip [new IP]

and then rebooting the device: ::

  $ artiq_coremgmt -D [old IP] reboot 

For Kasli-SoC: 
    If the ``ip`` config is not set, Kasli-SoC firmware defaults to using the IP address ``192.168.1.56``. It can then be changed with the procedure above. 

For Kasli or KC705: 
    If the ``ip`` config field is not set or set to ``use_dhcp``, the device will attempt to obtain an IP address and default gateway using DHCP. The chosen IP address will be in log output, which can be accessed via the :ref:`UART log <connecting-UART>`. If a static IP address is preferred, it can be flashed directly (OpenOCD must be installed and configured, as in :doc:`flashing`), along with, as necessary, default gateway, IPv6, and/or MAC address: ::

        $ artiq_mkfs flash_storage.img [-s mac xx:xx:xx:xx:xx:xx] [-s ip xx.xx.xx.xx/xx] [-s ipv4_default_route xx.xx.xx.xx] [-s ip6 xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx/xx] [-s ipv6_default_route xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx]
        $ artiq_flash -t [board] -V [variant] -f flash_storage.img storage start

On Kasli or Kasli SoC devices, specifying the MAC address is unnecessary, as they can obtain it from their EEPROM. If you only want to access the core device from the same subnet, default gateway and IPv4 prefix length may also be ommitted. Regardless of board, once a device is reachable by ``artiq_coremgmt``, any of these fields can be accessed using ``artiq_coremgmt config write`` and ``artiq_coremgt config read``; see also :ref:`Utilities <core-device-management-tool>`.  

Regarding IPv6, note that the device also has a link-local address that corresponds to its EUI-64, which can be used simultaneously to the (potentially unrelated) IPv6 address defined by using the ``ip6`` configuration key.

Check that you can ping the device. If ping fails, check that the Ethernet LED is ON; on Kasli, it is the LED next to the SFP0 connector. As a next step, try connecting to the serial port to read the UART log; see :ref:`connecting-UART`.  

.. _core-device-config: 

Configuring the core device
---------------------------

The following steps are optional, and you only need to execute them if they are necessary for your specific system. To learn more about how ARTIQ works and how to use it first, you might skip to the next page, :doc:`rtio`.

.. note:: 

  For every use of ``artiq_coremgmt``, the target IP address must be specified either with ``-D`` or in a correctly formatted :ref:`device database <device-db>` in the same directory. The core device generally needs to be restarted for changes to take effect. 

Flash idle and/or startup kernel
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The *idle kernel* is the kernel (that is, a piece of code running on the core device; see :doc:`the next page <rtio>` for further explanation) which the core device runs in between experiments and whenever not connected to the host. It is saved directly to the core device's flash storage in compiled form. Potential uses include cleanup of the environment between experiments, state maintenance for certain hardware, or anything else that should run continuously whenever the system is not otherwise occupied. 

To flash an idle kernel, first write an idle experiment. Note that since the idle kernel runs regardless of whether the core device is connected to the host, remote procedure calls or RPCs (functions called by a kernel to run on the host) are forbidden and the ``run()`` method must be a kernel marked with ``@kernel``. Once written, you can compile and flash your idle experiment: ::

  $ artiq_compile idle.py 
  $ artiq_coremgmt config write -f idle_kernel idle.elf

The *startup kernel* is a kernel executed once and only once immediately whenever the core device powers on. Uses include initializing DDSes and setting TTL directions. For DRTIO systems, the startup kernel should wait until the desired destinations, including local RTIO, are up, using ``self.core.get_rtio_destination_status`` (:meth:`~artiq.coredevice.core.Core.get_rtio_destination_status`). 

To flash a startup kernel, proceed as with the idle kernel, but using the ``startup_kernel`` key in the ``artiq_coremgmt`` command. 

.. note:: 
  Subkernels (see :doc:`using_drtio_subkernels`) are allowed in idle (and startup) experiments without any additional ceremony. ``artiq_compile`` will produce a ``.tar`` rather than a ``.elf``; simply substitute ``idle.tar`` for ``idle.elf`` in the ``artiq_coremgmt config write`` command. 

Select the RTIO clock source
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The core device may use any of an external clock signal, its internal clock with external frequency reference, or its internal clock with internal crystal reference. Clock source and timing are set at power-up. To find out what clock signal you are using, check the startup logs with ``artiq_coremgmt log``. 

The default is to use an internal 125MHz clock. To select a source, use a command of the form: ::

  $ artiq_coremgmt config write -s rtio_clock int_125  # internal 125MHz clock (default)
  $ artiq_coremgmt config write -s rtio_clock ext0_synth0_10to125  # external 10MHz reference used to synthesize internal 125MHz

See :ref:`core-device-clocking` for availability of specific options.    

Set up resolving RTIO channels to their names
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This feature allows you to print the channels' respective names alongside with their numbers in RTIO error messages. To enable it, run the ``artiq_rtiomap`` tool and write its result into the device config at the ``device_map`` key: ::

  $ artiq_rtiomap dev_map.bin
  $ artiq_coremgmt config write -f device_map dev_map.bin

More information on the ``artiq_rtiomap`` utility can be found on the :ref:`Utilities <rtiomap-tool>` page.

Enable event spreading 
^^^^^^^^^^^^^^^^^^^^^^

This feature changes the logic used for queueing RTIO output events in the core device for a more efficient use of FPGA resources, at the cost of introducing nondeterminism and potential unpredictability in certain timing errors (specifically gateware :ref:`sequence errors<sequence-errors>`). It can be enabled with the config key ``sed_spread_enable``. See :ref:`sed-event-spreading`.

Load the DRTIO routing table
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you are using DRTIO and the default routing table (for a star topology) is not suitable to your needs, you will first need to prepare and load a different routing table. See :ref:`Using DRTIO <drtio-routing>`.
