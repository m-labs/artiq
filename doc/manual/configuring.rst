Networking and configuration
============================

.. _core-device-networking:

Setting up core device networking
---------------------------------

For Kasli, insert a SFP/RJ45 transceiver (normally included with purchases from M-Labs and QUARTIQ) into the SFP0 port and connect it to an Ethernet port in your network. If the port is 10Mbps or 100Mbps and not 1000Mbps, make sure that the SFP/RJ45 transceiver supports the lower rate. Many SFP/RJ45 transceivers only support the 1000Mbps rate. If you do not have a SFP/RJ45 transceiver that supports 10Mbps and 100Mbps rates, you may instead use a gigabit Ethernet switch in the middle to perform rate conversion.

You can also insert other types of SFP transceivers into Kasli if you wish to use it directly in e.g. an optical fiber Ethernet network. Kasli-SoC already directly features RJ45 10/100/1000 Ethernet.

IP address and ping
^^^^^^^^^^^^^^^^^^^

If you purchased a Kasli or Kasli-SoC device from M-Labs, it will arrive with an IP address already set, normally the address requested in the web shop at time of purchase. If you did not specify an address at purchase, the default IP M-Labs uses is ``192.168.1.75``. If you did not obtain your hardware from M-Labs, or if you have just reflashed your core device, see :ref:`networking-tips` below.

Once you know the IP, check that you can ping your device: ::

  $ ping <IP_address>

If ping fails, check that the Ethernet LED is ON; on Kasli, it is the LED next to the SFP0 connector. As a next step, try connecting to the serial port to read the UART log. See :ref:`connecting-UART`.

Core management tool
^^^^^^^^^^^^^^^^^^^^

The tool used to configure the core device is the command-line utility :mod:`~artiq.frontend.artiq_coremgmt`. In order for it to connect to your core device, it is necessary to supply it somehow with the correct IP address for your core device. This can be done directly through use of the ``-D`` option, for example in: ::

    $ artiq_coremgmt -D <IP_address> log

.. note::
  This command reads and displays the core log. If you have recently rebooted or reflashed your core device, you should see the startup logs in your terminal.

Normally, however, the core device IP is supplied through the *device database* for your system, which comes in the form of a Python script called ``device_db.py`` (see also :ref:`device-db`). If you purchased a system from M-Labs, the ``device_db.py`` for your system will have been provided for you, either on the USB stick, inside ``~/artiq`` on your NUC, or sent by email.

Make sure the field ``core_addr`` at the top of the file is set to your core device's correct IP address, and always execute :mod:`~artiq.frontend.artiq_coremgmt` from the same directory the device database is placed in.

Once you can reach your core device, the IP can be changed at any time by running: ::

  $ artiq_coremgmt [-D old_IP] config write -s ip <new_IP>

and then rebooting the device: ::

  $ artiq_coremgmt [-D old_IP] reboot

Make sure to correspondingly edit your ``device_db.py`` after rebooting.

.. _networking-tips:

Tips and troubleshooting
^^^^^^^^^^^^^^^^^^^^^^^^
For Kasli-SoC:
    If the ``ip`` config is not set, Kasli-SoC firmware defaults to using the IP address ``192.168.1.56``.

For ZC706:
    If the ``ip`` config is not set, ZC706 firmware defaults to using the IP address ``192.168.1.52``.

For Kasli or KC705:
    If the ``ip`` config field is not set or set to ``use_dhcp``, the device will attempt to obtain an IP address and default gateway using DHCP. The chosen IP address will be in log output, which can be accessed via the :ref:`UART log <connecting-UART>`.

    If a static IP address is preferred, it can be flashed directly (OpenOCD must be installed and configured, as in :doc:`flashing`), along with, as necessary, default gateway, IPv6, and/or MAC address: ::

        $ artiq_mkfs flash_storage.img [-s mac xx:xx:xx:xx:xx:xx] [-s ip xx.xx.xx.xx/xx] [-s ipv4_default_route xx.xx.xx.xx] [-s ip6 xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx/xx] [-s ipv6_default_route xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx]
        $ artiq_flash -t [board] -V [variant] -f flash_storage.img storage start

On Kasli or Kasli-SoC devices, specifying the MAC address is unnecessary, as they can obtain it from their EEPROM. If you only want to access the core device from the same subnet, default gateway and IPv4 prefix length may also be ommitted. On any board, once a device can be reached by :mod:`~artiq.frontend.artiq_coremgmt`, these values can be set and edited at any time, following the procedure for IP above.

Regarding IPv6, note that the device also has a link-local address that corresponds to its EUI-64, which can be used simultaneously to the (potentially unrelated) IPv6 address defined by using the ``ip6`` configuration key.

If problems persist, see the :ref:`network troubleshooting <faq-networking>` section of the FAQ.

.. _core-device-config:

Configuring the core device
---------------------------

.. note::
  The following steps are optional, and you only need to execute them if they are necessary for your specific system. To learn more about how ARTIQ works and how to use it first, you might skip to the first tutorial page, :doc:`rtio`. For all configuration options, the core device generally must be restarted for changes to take effect.

Flash idle and/or startup kernel
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The *idle kernel* is the kernel (that is, a piece of code running on the core device; see :doc:`rtio` for further explanation) which the core device runs in between experiments and whenever not connected to the host. It is saved directly to the core device's flash storage in compiled form. Potential uses include cleanup of the environment between experiments, state maintenance for certain hardware, or anything else that should run continuously whenever the system is not otherwise occupied.

To flash an idle kernel, first write an idle experiment. Note that since the idle kernel runs regardless of whether the core device is connected to the host, remote procedure calls or RPCs (functions called by a kernel to run on the host) are forbidden and the ``run()`` method must be a kernel marked with ``@kernel``. Once written, you can compile and flash your idle experiment: ::

  $ artiq_compile idle.py
  $ artiq_coremgmt config write -f idle_kernel idle.elf

The *startup kernel* is a kernel executed once and only once immediately whenever the core device powers on. Uses include initializing DDSes and setting TTL directions. For DRTIO systems, the startup kernel should wait until the desired destinations, including local RTIO, are up, using ``self.core.get_rtio_destination_status`` (see :meth:`~artiq.coredevice.core.Core.get_rtio_destination_status`).

To flash a startup kernel, proceed as with the idle kernel, but using the ``startup_kernel`` key in the :mod:`~artiq.frontend.artiq_coremgmt` command.

.. note::
  Subkernels (see :doc:`using_drtio_subkernels`) are allowed in idle (and startup) experiments without any additional ceremony. :mod:`~artiq.frontend.artiq_compile` will produce a ``.tar`` rather than a ``.elf``; simply substitute ``idle.tar`` for ``idle.elf`` in the ``artiq_coremgmt config write`` command.

Select the RTIO clock source
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The core device may use any of an external clock signal, its internal clock with external frequency reference, or its internal clock with internal crystal reference. Clock source and timing are set at power-up. To find out what clock signal you are using, check the startup logs with ``artiq_coremgmt log``.

The default is to use an internal 125MHz clock. To select a source, use a command of the form: ::

  $ artiq_coremgmt config write -s rtio_clock int_125  # internal 125MHz clock (default)
  $ artiq_coremgmt config write -s rtio_clock ext0_synth0_10to125  # external 10MHz reference used to synthesize internal 125MHz

See :ref:`core-device-clocking` for availability of specific options.

.. _config-rtiomap:

Set up resolving RTIO channels to their names
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This feature allows you to print the channels' respective names alongside with their numbers in RTIO error messages. To enable it, run the :mod:`~artiq.frontend.artiq_rtiomap` tool and write its result into the device config at the ``device_map`` key: ::

  $ artiq_rtiomap dev_map.bin
  $ artiq_coremgmt config write -f device_map dev_map.bin

More information on the ``artiq_rtiomap`` utility can be found on the :ref:`Utilities <rtiomap-tool>` page.

Enable event spreading
^^^^^^^^^^^^^^^^^^^^^^

This feature changes the logic used for queueing RTIO output events in the core device for a more efficient use of FPGA resources, at the cost of introducing nondeterminism and potential unpredictability in certain timing errors (specifically gateware :ref:`sequence errors<sequence-errors>`). It can be enabled with the config key ``sed_spread_enable``. See :ref:`sed-event-spreading`.

Load the DRTIO routing table
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you are using DRTIO and the default routing table (for a star topology) is not suitable to your needs, you will first need to prepare and load a different routing table. See :ref:`Using DRTIO <drtio-routing>`.
