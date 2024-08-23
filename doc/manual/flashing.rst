(Re)flashing your core device
=============================

.. note::
  If you have purchased a pre-assembled system from M-Labs or QUARTIQ, the gateware and firmware of your devices will already be flashed to the newest version of ARTIQ. Flashing your device is only necessary if you obtained your hardware in a different way, or if you want to change your system configuration or upgrade your ARTIQ version after the original purchase. Otherwise, skip straight to :doc:`configuring`.

.. _obtaining-binaries:

Obtaining board binaries
------------------------

If you have an active firmware subscription with M-Labs or QUARTIQ, you can obtain firmware for your system that corresponds to your currently installed version of ARTIQ using the ARTIQ firmware service (AFWS). One year of subscription is included with most hardware purchases. You may purchase or extend firmware subscriptions by writing to the sales@ email. The client :mod:`~artiq.frontend.afws_client` is included in all ARTIQ installations.

Run the command::

  $ afws_client <username> build <afws_director> <variant>

Replace ``<username>`` with the login name that was given to you with the subscription, ``<variant>`` with the name of your system variant, and ``<afws_directory>`` with the name of an empty directory, which will be created by the command if it does not exist. Enter your password when prompted and wait for the build (if applicable) and download to finish. If you experience issues with the AFWS client, write to the helpdesk@ email. For more information about :mod:`~artiq.frontend.afws_client` see also the corresponding entry on the :ref:`Utilities <afws-client>` page.

For certain configurations (KC705 or ZC706 only) it is also possible to source firmware from `the M-Labs Hydra server <https://nixbld.m-labs.hk/project/artiq>`_ (in ``main`` and ``zynq`` respectively).

Without a subscription, you may build the firmware yourself from the open source code. See the section :doc:`building_developing`.

Installing and configuring OpenOCD
----------------------------------

.. warning::
  These instructions are not applicable to Zynq devices (Kasli-SoC or ZC706), which do not use the utility :mod:`~artiq.frontend.artiq_flash`. If your core device is a Zynq device, skip straight to :ref:`writing-flash`.

ARTIQ supplies the utility :mod:`~artiq.frontend.artiq_flash`, which uses OpenOCD to write the binary images into an FPGA board's flash memory. For both Nix and MSYS2, OpenOCD are included with the installation by default. Note that in the case of Nix this is the package ``artiq.openocd-bscanspi`` and not ``pkgs.openocd``; the second is OpenOCD from the Nix package collection, which does not support ARTIQ/Sinara boards.

.. note::

    With Conda, install ``openocd`` as follows: ::

        $ conda install -c m-labs openocd

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

First ensure the board is connected to your computer. In the case of Kasli, the JTAG adapter is integrated into the Kasli board; for flashing (and debugging) you can simply connect your computer to the micro-USB connector on the Kasli front panel. For Kasli-SoC, which uses :mod:`~artiq.frontend.artiq_coremgmt` to flash over network, an Ethernet connection and an IP address, supplied either with the ``-D`` option or in your :ref:`device database <device-db>`, are sufficient.

For Kasli-SoC or ZC706:
    ::

        $ artiq_coremgmt [-D IP_address] config write -f boot <afws_directory>/boot.bin
        $ artiq_coremgmt reboot

    If the device is not reachable due to corrupted firmware or networking problems, extract the SD card and copy ``boot.bin`` onto it manually.

For Kasli:
    ::

        $ artiq_flash -d <afws_directory>

For KC705:
    ::

        $ artiq_flash -t kc705 -d <afws_directory>

    The SW13 switches need to be set to 00001.

Flashing over network is also possible for Kasli and KC705, assuming IP networking has already been set up. In this case, the ``-H HOSTNAME`` option is used; see the entry for :mod:`~artiq.frontend.artiq_flash` in the :ref:`Utilities <flashing-loading-tool>` reference.

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
