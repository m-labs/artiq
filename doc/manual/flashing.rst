(Re)flashing the core device 
============================

.. _reflashing-core-device:

Reflashing core device gateware and firmware
--------------------------------------------

.. note::
  If you have purchased a pre-assembled system from M-Labs or QUARTIQ, the gateware and firmware of your devices will already be flashed to the newest version of ARTIQ. These steps are only necessary if you obtained your hardware in a different way, or if you want to change your system configuration or upgrade your ARTIQ version after the original purchase.  


Obtaining the board binaries
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you have an active firmware subscription with M-Labs or QUARTIQ, you can obtain firmware for your system that corresponds to your currently installed version of ARTIQ using AFWS (ARTIQ firmware service). One year of subscription is included with most hardware purchases. You may purchase or extend firmware subscriptions by writing to the sales@ email.

Run the command::

  $ afws_client [username] build [afws_directory] [variant]

Replace ``[username]`` with the login name that was given to you with the subscription, ``[variant]`` with the name of your system variant, and ``[afws_directory]`` with the name of an empty directory, which will be created by the command if it does not exist. Enter your password when prompted and wait for the build (if applicable) and download to finish. If you experience issues with the AFWS client, write to the helpdesk@ email.

For certain configurations (KC705 or ZC705 only) it is also possible to source firmware from `the M-Labs Hydra server <https://nixbld.m-labs.hk/project/artiq>`_ (in ``main`` and ``zynq`` respectively).

Without a subscription, you may build the firmware yourself from the open source code. See the section :ref:`Developing ARTIQ <developing-artiq>`.

.. _installing-configuring-openocd:

Installing and configuring OpenOCD
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. note::
  These instructions are not applicable to Kasli-SoC, which does not use the utility ``artiq_flash`` to reflash. If your core device is a Kasli SoC, skip straight to :ref:`writing-flash`. 

ARTIQ supplies the utility ``artiq_flash``, which uses OpenOCD to write the binary images into an FPGA board's flash memory. 

* With Nix, add ``aqmain.openocd-bscanspi`` to the shell packages. Be careful not to add ``pkgs.openocd`` instead - this would install OpenOCD from the NixOS package collection, which does not support ARTIQ boards.

* With MSYS2, ``openocd`` and ``bscan-spi-bitstreams`` are included with ``artiq`` by default.

* With Conda, install ``openocd`` as follows::

    $ conda install -c m-labs openocd

Some additional steps are necessary to ensure that OpenOCD can communicate with the FPGA board:

*  On Linux, first ensure that the current user belongs to the ``plugdev`` group (i.e. ``plugdev`` shown when you run ``$ groups``). If it does not, run ``$ sudo adduser $USER plugdev`` and re-login.

If you installed OpenOCD on Linux using Nix, use the ``which`` command to determine the path to OpenOCD, and then copy the udev rules: ::

  $ which openocd
  /nix/store/2bmsssvk3d0y5hra06pv54s2324m4srs-openocd-mlabs-0.10.0/bin/openocd
  $ sudo cp /nix/store/2bmsssvk3d0y5hra06pv54s2324m4srs-openocd-mlabs-0.10.0/share/openocd/contrib/60-openocd.rules /etc/udev/rules.d
  $ sudo udevadm trigger

NixOS users should of course configure OpenOCD through ``/etc/nixos/configuration.nix`` instead.

If you installed OpenOCD on Linux using Conda and are using the Conda environment ``artiq``, then execute the statements below. If you are using a different environment, you will have to replace ``artiq`` with the name of your environment::

  $ sudo cp ~/.conda/envs/artiq/share/openocd/contrib/60-openocd.rules /etc/udev/rules.d
  $ sudo udevadm trigger

* On Windows, a third-party tool, `Zadig <http://zadig.akeo.ie/>`_, is necessary. It is also included with the MSYS2 offline installer and available from the Start Menu as ``Zadig Driver Installer``. Use it as follows:

1. Make sure the FPGA board's JTAG USB port is connected to your computer.
2. Activate Options → List All Devices.
3. Select the "Digilent Adept USB Device (Interface 0)" or "FTDI Quad-RS232 HS" (or similar)
   device from the drop-down list.
4. Select WinUSB from the spinner list.
5. Click "Install Driver" or "Replace Driver".

You may need to repeat these steps every time you plug the FPGA board into a port where it has not been plugged into previously on the same system.

.. _writing-flash:

Writing the flash
^^^^^^^^^^^^^^^^^

First ensure the board is connected to your computer. In the case of Kasli, the JTAG adapter is integrated into the Kasli board; for flashing (and debugging) you simply need to connect your computer to the micro-USB connector on the Kasli front panel. For Kasli-SoC, which uses ``artiq_coremgmt``, an IP address supplied either with the ``-D`` option or in a correctly specified ``device_db.py`` suffices. 

* For Kasli-SoC::

      $ artiq_coremgmt [-D 192.168.1.75] config write -f boot [afws_directory]/boot.bin

If the Kasli-SoC won't boot due to nonexistent or corrupted firmware, extract the SD card and copy ``boot.bin`` onto it manually.

* For Kasli::

      $ artiq_flash -d [afws_directory]

* For the KC705 board::

    $ artiq_flash -t kc705 -d [afws_directory]

  The SW13 switches need to be set to 00001.

Flashing over network is also possible for Kasli and KC705, assuming IP networking has already been set up. In this case, the ``-H HOSTNAME`` option is used; see the entry for ``artiq_flash`` in the :ref:`Utilities <flashing-loading-tool>` reference. 