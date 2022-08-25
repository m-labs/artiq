Installing ARTIQ
================

ARTIQ can be installed using the Nix (on Linux) or Conda (on Windows or Linux) package managers.

Nix is an innovative, robust, fast, and high-quality solution that comes with a larger collection of packages and features than Conda. However, Windows support is poor (using it with Windows Subsystem for Linux still has many problems) and Nix can be harder to learn.

Conda has a more traditional approach to package management, is much more limited, slow, and lower-quality than Nix, but it supports Windows and it is simpler to use when it functions correctly.

In the current state of affairs, we recommend that Linux users install ARTIQ via Nix and Windows users install it via Conda.

.. _installing-nix-users:

Installing via Nix (Linux)
--------------------------

First, install the Nix package manager. Some distributions provide a package for the Nix package manager, otherwise, it can be installed via the script on the `Nix website <http://nixos.org/nix/>`_. Make sure you get Nix version 2.4 or higher.

Once Nix is installed, enable Flakes: ::

  $ mkdir -p ~/.config/nix
  $ echo "experimental-features = nix-command flakes" > ~/.config/nix/nix.conf

The easiest way to obtain ARTIQ is then to install it into the user environment with ``$ nix profile install git+https://github.com/m-labs/artiq.git``. Answer "Yes" to the questions about setting Nix configuration options. This provides a minimal installation of ARTIQ where the usual commands (``artiq_master``, ``artiq_dashboard``, ``artiq_run``, etc.) are available.

This installation is however quite limited, as Nix creates a dedicated Python environment for the ARTIQ commands alone. This means that other useful Python packages that you may want (pandas, matplotlib, ...) are not available to them.

Installing multiple packages and making them visible to the ARTIQ commands requires using the Nix language. Create an empty directory with a file ``flake.nix`` with the following contents:

::

  {
    inputs.artiq.url = "git+https://github.com/m-labs/artiq.git";
    inputs.extrapkg.url = "git+https://git.m-labs.hk/M-Labs/artiq-extrapkg.git";
    inputs.extrapkg.inputs.artiq.follows = "artiq";
    outputs = { self, artiq, extrapkg }:
      let
        pkgs = artiq.inputs.nixpkgs.legacyPackages.x86_64-linux;
        aqmain = artiq.packages.x86_64-linux;
        aqextra = extrapkg.packages.x86_64-linux;
      in {
        defaultPackage.x86_64-linux = pkgs.buildEnv {
          name = "artiq-env";
          paths = [
            # ========================================
            # EDIT BELOW
            # ========================================
            (pkgs.python3.withPackages(ps: [
              # List desired Python packages here.
              aqmain.artiq
              #ps.paramiko  # needed if and only if flashing boards remotely (artiq_flash -H)
              #aqextra.flake8-artiq

              # The NixOS package collection contains many other packages that you may find
              # interesting. Here are some examples:
              #ps.pandas
              #ps.numpy
              #ps.scipy
              #ps.numba
              #ps.matplotlib
              # or if you need Qt (will recompile):
              #(ps.matplotlib.override { enableQt = true; })
              #ps.bokeh
              #ps.cirq
              #ps.qiskit
            ]))
            #aqextra.korad_ka3005p
            #aqextra.novatech409b
            # List desired non-Python packages here
            #aqmain.openocd-bscanspi  # needed if and only if flashing boards
            # Other potentially interesting packages from the NixOS package collection:
            #pkgs.gtkwave
            #pkgs.spyder
            #pkgs.R
            #pkgs.julia
            # ========================================
            # EDIT ABOVE
            # ========================================
          ];
        };
      };
  }


Then spawn a shell containing the packages with ``$ nix shell``. The ARTIQ commands with all the additional packages should now be available.

You can exit the shell by typing Control-D. The next time ``$ nix shell`` is invoked, Nix uses the cached packages so the shell startup is fast.

You can create directories containing each a ``flake.nix`` that correspond to different sets of packages. If you are familiar with Conda, using Nix in this way is similar to having multiple Conda environments.

If your favorite package is not available with Nix, contact us using the helpdesk@ email.

Installing via Conda (Windows, Linux)
-------------------------------------

.. warning::
  For Linux users, the Nix package manager is preferred, as it is more reliable and faster than Conda.

First, install `Anaconda <https://www.anaconda.com/distribution/>`_ or the more minimalistic `Miniconda <https://conda.io/en/latest/miniconda.html>`_.

After installing either Anaconda or Miniconda, open a new terminal (also known as command line, console, or shell and denoted here as lines starting with ``$``) and verify the following command works::

    $ conda

Executing just ``conda`` should print the help of the ``conda`` command. If your shell does not find the ``conda`` command, make sure that the Conda binaries are in your ``$PATH``. If ``$ echo $PATH`` does not show the Conda directories, add them: execute ``$ export PATH=$HOME/miniconda3/bin:$PATH`` if you installed Conda into ``~/miniconda3``.

Controllers for third-party devices (e.g. Thorlabs TCube, Lab Brick Digital Attenuator, etc.) that are not shipped with ARTIQ can also be installed with this script. Browse `Hydra <https://nixbld.m-labs.hk/project/artiq>`_ or see the list of NDSPs in this manual to find the names of the corresponding packages, and list them at the beginning of the script.

Set up the Conda channel and install ARTIQ into a new Conda environment: ::

    $ conda config --prepend channels https://conda.m-labs.hk/artiq-beta
    $ conda config --append channels conda-forge
    $ conda create -n artiq artiq

.. note::
  If you do not need to flash boards, the ``artiq`` package is sufficient. The packages named ``artiq-board-*`` contain only firmware for the FPGA board, and you should not install them unless you are reflashing an FPGA board. Controllers for third-party devices (e.g. Thorlabs TCube, Lab Brick Digital Attenuator, etc.) that are not shipped with ARTIQ can also be installed with Conda. Browse `Hydra <https://nixbld.m-labs.hk/project/artiq>`_ or see the list of NDSPs in this manual to find the names of the corresponding packages.

After the installation, activate the newly created environment by name. ::

    $ conda activate artiq

This activation has to be performed in every new shell you open to make the ARTIQ tools from that environment available.

.. note::
    Some ARTIQ examples also require matplotlib and numba, and they must be installed manually for running those examples. They are available in Conda.

Upgrading ARTIQ (with Nix)
--------------------------

Run ``$ nix profile upgrade`` if you installed ARTIQ into your user profile. If you used a ``flake.nix`` shell environment, make a back-up copy of the ``flake.lock`` file to enable rollback, then run ``$ nix flake update`` and re-enter ``$ nix shell``.

To rollback to the previous version, respectively use ``$ nix profile rollback`` or restore the backed-up version of the ``flake.lock`` file.

You may need to reflash the gateware and firmware of the core device to keep it synchronized with the software.

Upgrading ARTIQ (with Conda)
----------------------------

When upgrading ARTIQ or when testing different versions it is recommended that new Conda environments are created instead of upgrading the packages in existing environments.
Keep previous environments around until you are certain that they are not needed anymore and a new environment is known to work correctly.

To install the latest version, just select a different environment name and run the installation command again.

Switching between Conda environments using commands such as ``$ conda deactivate artiq-6`` and ``$ conda activate artiq-5`` is the recommended way to roll back to previous versions of ARTIQ.

You may need to reflash the gateware and firmware of the core device to keep it synchronized with the software.

You can list the environments you have created using::

    $ conda env list

Flashing gateware and firmware into the core device
---------------------------------------------------

.. note::
  If you have purchased a pre-assembled system from M-Labs or QUARTIQ, the gateware and firmware are already flashed and you can skip those steps, unless you want to replace them with a different version of ARTIQ.

You need to write three binary images onto the FPGA board:

1. The FPGA gateware bitstream
2. The bootloader
3. The ARTIQ runtime or satellite manager

Installing OpenOCD
^^^^^^^^^^^^^^^^^^

.. note::
  This version of OpenOCD is not applicable to Kasli-SoC.

OpenOCD can be used to write the binary images into the core device FPGA board's flash memory.

With Nix, add ``aqmain.openocd-bscanspi`` to the shell packages. Be careful not to add ``pkgs.openocd`` instead - this would install OpenOCD from the NixOS package collection, which does not support ARTIQ boards.

With Conda, install ``openocd`` as follows::

    $ conda install -c m-labs openocd

.. _configuring-openocd:

Configuring OpenOCD
^^^^^^^^^^^^^^^^^^^

.. note::
  These instructions are not applicable to Kasli-SoC.

Some additional steps are necessary to ensure that OpenOCD can communicate with the FPGA board.

On Linux, first ensure that the current user belongs to the ``plugdev`` group (i.e. ``plugdev`` shown when you run ``$ groups``). If it does not, run ``$ sudo adduser $USER plugdev`` and re-login.

If you installed OpenOCD on Linux using Nix, use the ``which`` command to determine the path to OpenOCD, and then copy the udev rules: ::

  $ which openocd
  /nix/store/2bmsssvk3d0y5hra06pv54s2324m4srs-openocd-mlabs-0.10.0/bin/openocd
  $ sudo cp /nix/store/2bmsssvk3d0y5hra06pv54s2324m4srs-openocd-mlabs-0.10.0/share/openocd/contrib/60-openocd.rules /etc/udev/rules.d
  $ sudo udevadm trigger

NixOS users should of course configure OpenOCD through ``/etc/nixos/configuration.nix`` instead.

If you installed OpenOCD on Linux using Conda and are using the Conda environment ``artiq``, then execute the statements below. If you are using a different environment, you will have to replace ``artiq`` with the name of your environment::

  $ sudo cp ~/.conda/envs/artiq/share/openocd/contrib/60-openocd.rules /etc/udev/rules.d
  $ sudo udevadm trigger

On Windows, a third-party tool, `Zadig <http://zadig.akeo.ie/>`_, is necessary. Use it as follows:

1. Make sure the FPGA board's JTAG USB port is connected to your computer.
2. Activate Options → List All Devices.
3. Select the "Digilent Adept USB Device (Interface 0)" or "FTDI Quad-RS232 HS" (or similar)
   device from the drop-down list.
4. Select WinUSB from the spinner list.
5. Click "Install Driver" or "Replace Driver".

You may need to repeat these steps every time you plug the FPGA board into a port where it has not been plugged into previously on the same system.

Obtaining the board binaries
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you have an active firmware subscription with M-Labs or QUARTIQ, you can obtain firmware that corresponds to the currently installed version of ARTIQ using AFWS (ARTIQ firmware service). One year of subscription is included with most hardware purchases. You may purchase or extend firmware subscriptions by writing to the sales@ email.

Run the command::

  $ afws_client [username] build [afws_directory] [variant]

Replace ``[username]`` with the login name that was given to you with the subscription, ``[variant]`` with the name of your system variant, and ``[afws_directory]`` with the name of an empty directory, which will be created by the command if it does not exist. Enter your password when prompted and wait for the build (if applicable) and download to finish. If you experience issues with the AFWS client, write to the helpdesk@ email.

Without a subscription, you may build the firmware yourself from the open source code. See the section :ref:`Developing ARTIQ <developing-artiq>`.

Writing the flash
^^^^^^^^^^^^^^^^^

Then, you can write the flash:

* For Kasli::

      $ artiq_flash -d [afws_directory]

The JTAG adapter is integrated into the Kasli board; for flashing (and debugging) you simply need to connect your computer to the micro-USB connector on the Kasli front panel.

* For Kasli-SoC::

      $ artiq_coremgmt [-D 192.168.1.75] config write -f boot [afws_directory]/boot.bin

If the Kasli-SoC won't boot due to corrupted firmware and ``artiq_coremgmt`` cannot access it, extract the SD card and replace ``boot.bin`` manually.

* For the KC705 board::

    $ artiq_flash -t kc705 -d [afws_directory]

  The SW13 switches need to be set to 00001.

Setting up the core device IP networking
----------------------------------------

For Kasli, insert a SFP/RJ45 transceiver (normally included with purchases from M-Labs and QUARTIQ) into the SFP0 port and connect it to an Ethernet port in your network. If the port is 10Mbps or 100Mbps and not 1000Mbps, make sure that the SFP/RJ45 transceiver supports the lower rate. Many SFP/RJ45 transceivers only support the 1000Mbps rate. If you do not have a SFP/RJ45 transceiver that supports 10Mbps and 100Mbps rates, you may instead use a gigabit Ethernet switch in the middle to perform rate conversion.

You can also insert other types of SFP transceivers into Kasli if you wish to use it directly in e.g. an optical fiber Ethernet network.

If you purchased a Kasli device from M-Labs, it usually comes with the IP address ``192.168.1.75``. Once you can reach this IP, it can be changed with: ::

  $ artiq_coremgmt -D 192.168.1.75 config write -s ip [new IP]

and then reboot the device (with ``artiq_flash start`` or a power cycle).

If the ip config field is not set, or set to "use_dhcp" then the device will attempt to obtain an IP address using
DHCP. If a static IP address is wanted, install OpenOCD as before, and flash the IP (and, if necessary, MAC) addresses
directly: ::

  $ artiq_mkfs flash_storage.img -s mac xx:xx:xx:xx:xx:xx -s ip xx.xx.xx.xx
  $ artiq_flash -t [board] -V [variant] -f flash_storage.img storage start

For Kasli devices, flashing a MAC address is not necessary as they can obtain it from their EEPROM.

If DHCP has been used the address can be found in the console output, which can be viewed using: ::

  $ python -m misoc.tools.flterm /dev/ttyUSB2

Check that you can ping the device. If ping fails, check that the Ethernet link LED is ON - on Kasli, it is the LED next to the SFP0 connector. As a next step, look at the messages emitted on the UART during boot. Use a program such as flterm or PuTTY to connect to the device's serial port at 115200bps 8-N-1 and reboot the device. On Kasli, the serial port is on FTDI channel 2 with v1.1 hardware (with channel 0 being JTAG) and on FTDI channel 1 with v1.0 hardware.

If you want to use IPv6, the device also has a link-local address that corresponds to its EUI-64, and an additional arbitrary IPv6 address can be defined by using the ``ip6`` configuration key. All IPv4 and IPv6 addresses can be used at the same time.

Miscellaneous configuration of the core device
----------------------------------------------

Those steps are optional. The core device usually needs to be restarted for changes to take effect.

* Load the idle kernel

The idle kernel is the kernel (some piece of code running on the core device) which the core device runs whenever it is not connected to a PC via Ethernet.
This kernel is therefore stored in the :ref:`core device configuration flash storage <core-device-flash-storage>`.

To flash the idle kernel, first compile the idle experiment. The idle experiment's ``run()`` method must be a kernel: it must be decorated with the ``@kernel`` decorator (see :ref:`next topic <connecting-to-the-core-device>` for more information about kernels). Since the core device is not connected to the PC, RPCs (calling Python code running on the PC from the kernel) are forbidden in the idle experiment. Then write it into the core device configuration flash storage: ::

  $ artiq_compile idle.py
  $ artiq_coremgmt config write -f idle_kernel idle.elf

.. note:: You can find more information about how to use the ``artiq_coremgmt`` utility on the :ref:`Utilities <core-device-management-tool>` page.

* Load the startup kernel

The startup kernel is executed once when the core device powers up. It should initialize DDSes, set up TTL directions, etc. Proceed as with the idle kernel, but using the ``startup_kernel`` key in the ``artiq_coremgmt`` command.

For DRTIO systems, the startup kernel should wait until the desired destinations (including local RTIO) are up, using :meth:`artiq.coredevice.Core.get_rtio_destination_status`.

* Load the DRTIO routing table

If you are using DRTIO and the default routing table (for a star topology) is not suitable to your needs, prepare and load a different routing table. See :ref:`Using DRTIO <using-drtio>`.

* Select the RTIO clock source (KC705 and Kasli)

The KC705 may use either an external clock signal, or its internal clock with external frequency or internal crystal reference. The clock is selected at power-up. Setting the RTIO clock source to "ext0_bypass" would bypass the Si5324 synthesiser, requiring that an input clock be present. To select the source, use one of these commands: ::

  $ artiq_coremgmt config write -s rtio_clock int_125  # internal 125MHz clock (default)
  $ artiq_coremgmt config write -s rtio_clock ext0_bypass  # external clock (bypass)

Other options include:
  - ``ext0_synth0_10to125`` - external 10MHz reference clock used by Si5324 to synthesize a 125MHz RTIO clock,
  - ``ext0_synth0_100to125`` - exteral 100MHz reference clock used by Si5324 to synthesize a 125MHz RTIO clock,
  - ``ext0_synth0_125to125`` - exteral 125MHz reference clock used by Si5324 to synthesize a 125MHz RTIO clock,
  - ``int_100`` - internal crystal reference is used by Si5324 to synthesize a 100MHz RTIO clock,
  - ``int_150`` - internal crystal reference is used by Si5324 to synthesize a 150MHz RTIO clock.
  - ``ext0_bypass_125`` and ``ext0_bypass_100`` - explicit aliases for ``ext0_bypass``.

Availability of these options depends on the board and their configuration - specific setting may or may not be supported.
