(Re)flashing your core device
=============================

.. note::
  If you have purchased a pre-assembled system from M-Labs or QUARTIQ, the gateware and firmware of your devices will already be flashed to the newest version of ARTIQ. Flashing your device is only necessary if you obtained your hardware in a different way, or if you want to change your system configuration or upgrade your ARTIQ version after the original purchase. Otherwise, skip straight to :doc:`configuring`.

.. _obtaining-binaries:

Obtaining board binaries
------------------------

If you have an active firmware subscription with M-Labs or QUARTIQ, you can obtain firmware for your system that corresponds to your currently installed version of ARTIQ using the ARTIQ firmware service (AFWS). One year of subscription is included with most hardware purchases. You may purchase or extend firmware subscriptions by writing to the sales@ email. The client :mod:`~artiq.frontend.afws_client` is included in all ARTIQ installations.

Run the command::

  $ afws_client <username> build <afws_directory> <variant>

Replace ``<username>`` with the login name that was given to you with the subscription, ``<variant>`` with the name of your system variant, and ``<afws_directory>`` with the name of an empty directory, which will be created by the command if it does not exist. Enter your password when prompted and wait for the build (if applicable) and download to finish. If you experience issues with the AFWS client, write to the helpdesk@ email. For more information about :mod:`~artiq.frontend.afws_client` see also the corresponding entry on the :ref:`Utilities <afws-client>` page.

For :ref:`hardcoded variant devices <devices-table>` it is also possible to source firmware from `the M-Labs Hydra server <https://nixbld.m-labs.hk/project/artiq>`_ (in ``main`` and ``zynq``).

Without a subscription, you may build the firmware yourself from the open source code. See the section :doc:`building_developing`.

Installing and configuring OpenOCD
----------------------------------

.. warning::
  These instructions are not applicable to :ref:`Zynq devices <devices-table>`, which do not use the utility :mod:`~artiq.frontend.artiq_flash`. If your core device is a Zynq device, skip straight to :ref:`writing-flash`.

ARTIQ supplies the utility :mod:`~artiq.frontend.artiq_flash`, which uses OpenOCD to write the binary images into an FPGA board's flash memory. With MSYS2, OpenOCD is included with the installation by default. For Nix, make sure to include the package ``artiq.openocd-bscanspi`` in your flake (in the :ref:`example custom flake <example-flake>`, you can simply uncomment the relevant line). Alternatively, you can use the ARTIQ main flake's development shell. Nix profile installations do not include OpenOCD.

Note that this is **not** ``pkgs.openocd``; the latter is OpenOCD from the Nix package collection, which does not support ARTIQ/Sinara boards.

.. tip::

  The development shell is an alternative, non-minimal ARTIQ environment which includes additional tools for working with ARTIQ, including OpenOCD. You can enter it with: ::

  $ nix develop git+https://github.com/m-labs/artiq.git

  However, unless you want the full development environment, it's usually preferable to use a lighter custom flake, such as the example in :doc:`installing`.

Some additional steps are necessary to ensure that OpenOCD can communicate with the FPGA board:

On Linux
^^^^^^^^

  First ensure that the current user belongs to the ``plugdev`` group (i.e. ``plugdev`` shown when you run ``$ groups``). If it does not, run ``$ sudo adduser $USER plugdev`` and re-login.

  If you installed OpenOCD on Linux using Nix, use the ``which`` command to determine the path to OpenOCD, and then copy the udev rules: ::

    $ which openocd
    /nix/store/2bmsssvk3d0y5hra06pv54s2324m4srs-openocd-mlabs-0.10.0/bin/openocd
    $ sudo cp /nix/store/2bmsssvk3d0y5hra06pv54s2324m4srs-openocd-mlabs-0.10.0/share/openocd/contrib/60-openocd.rules /etc/udev/rules.d
    $ sudo udevadm trigger

  NixOS users should configure OpenOCD through ``/etc/nixos/configuration.nix`` instead.

Linux using Conda
^^^^^^^^^^^^^^^^^

  .. note::

    With Conda, install OpenOCD as follows: ::

      $ conda install -c m-labs openocd

  If you are using a Conda environment ``artiq``, then execute the statements below. If you are using a different environment, you will have to replace ``artiq`` with the name of your environment::

    $ sudo cp ~/.conda/envs/artiq/share/openocd/contrib/60-openocd.rules /etc/udev/rules.d
    $ sudo udevadm trigger

On Windows
^^^^^^^^^^

  A third-party tool, `Zadig <http://zadig.akeo.ie/>`_, is necessary. It is also included with the MSYS2 offline installer and available from the Start Menu as ``Zadig Driver Installer``. Use it as follows:

    1. Make sure the FPGA board's JTAG USB port is connected to your computer.
    2. Activate Options → List All Devices.
    3. Select the "Digilent Adept USB Device (Interface 0)" or "FTDI Quad-RS232 HS" (or similar)
       device from the drop-down list.
    4. Select WinUSB from the spinner list.
    5. Click "Install Driver" or "Replace Driver".

  You may need to repeat these steps every time you plug the FPGA board into a port it has not previously been plugged into, even on the same system.

.. _writing-flash:

Writing the flash
-----------------

If your device is already accessible over the network, all you need is an Ethernet connection and a correct IP address (supplied either with the ``-D`` option or in :ref:`your device database <device-db>`). ::

    $ artiq_coremgmt [-D IP_address] flash <afws_directory>
    $ artiq_coremgmt [-D IP_address] reboot

If the device is not reachable due to corrupted firmware or networking problems, binaries can be loaded manually. On Kasli or KC705, connect the board directly to your computer by JTAG USB and use :mod:`~artiq.frontend.artiq_flash`, as follows: ::

        $ artiq_flash [-t kc705] -d <afws_directory>

Note the micro-USB in the Kasli front panel. On KC705, the SW13 switches need to be set to 00001.

For Zynq devices (Kasli-SoC, ZC706 or EBAZ4205), extract the SD card and copy ``boot.bin`` onto it manually.

Writing to satellite devices
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Satellite devices can at any time be flashed directly through the SD card or :mod:`~artiq.frontend.artiq_flash`, as applicable. Satellite devices do not support individual networking and do not have IP addresses. If your DRTIO system is up and running and the routing table is in place, on the other hand, they can be flashed through the master's network connection: ::

  $ artiq_coremgmt [-D IP_address] -s <destination_number> flash <afws_directory>

.. _connecting-uart:

Connecting to the UART log
--------------------------

A UART is a peripheral device for asynchronous serial communication; in the case of core device boards, it allows the reading of the UART log, which is used for debugging, especially when problems with booting or networking disallow checking core logs with ``artiq_coremgmt log``. If you had no issues flashing your board you can proceed directly to :doc:`configuring`.

Otherwise, ensure your core device is connected to your PC with a data micro-USB cable, as above, and wait at least fifteen seconds after startup to try to connect. To help find the correct port to connect to, you can list your system's serial devices by running: ::

  $ python -m serial.tools.list_ports -v

This will give you the list of ``/dev/ttyUSBx`` or ``COMx`` device names (on Linux and Windows respectively). Most commonly, the correct option is the third, i.e. index number 2, but it can vary.

On Linux:
  Run the commands: ::

    stty 115200 < /dev/ttyUSBx
    cat /dev/ttyUSBx

  When you restart or reflash the core device you should see the startup logs in the terminal. If you encounter issues, try other ``ttyUSBx`` names, and make certain that your user is part of the ``dialout`` group (run ``groups`` in a terminal to check).

On Windows:
  Use a program such as PuTTY to connect to the COM port. Connect to every available COM port at first, restart the core device, see which port produces meaningful output, and close the others. It may be necessary to install the `FTDI drivers <https://ftdichip.com/drivers/>`_ first.

Note that the correct parameters for the serial port are 115200bps 8-N-1 for every core device.
