Installing ARTIQ
================

ARTIQ can be installed using the Nix (on Linux) or Conda (on Windows or Linux) package managers.

Nix is an innovative, robust, fast, and high-quality solution that comes with a larger collection of packages and features than Conda. However, Windows support is poor (using it with Windows Subsystem for Linux still has many problems) and Nix can be harder to learn.

Conda has a more traditional approach to package management, is much more limited, slow, and lower-quality than Nix, but it supports Windows and it is simpler to use when it functions correctly.

In the current state of affairs, we recommend that Linux users install ARTIQ via Nix and Windows users install it via Conda.

.. _installing-nix-users:

Installing via Nix (Linux)
--------------------------

.. note::
  Make sure you are using a 64-bit x86 Linux system. If you are using other systems, such as 32-bit x86, Nix will attempt to compile a number of dependencies from source on your machine. This may work, but the installation process will use a lot of CPU time, memory, and disk space.

First, install the Nix package manager. Some distributions provide a package for the Nix package manager, otherwise, it can be installed via the script on the `Nix website <http://nixos.org/nix/>`_.

Once Nix is installed, add the M-Labs package channel with: ::

  $ nix-channel --add https://nixbld.m-labs.hk/channel/custom/artiq/full-beta/artiq-full

Those channels track `nixpkgs 19.09 <https://github.com/NixOS/nixpkgs/tree/release-19.09>`_. You can check the latest status through the `Hydra interface <https://nixbld.m-labs.hk>`_. As the Nix package manager default installation uses the development version of nixpkgs, we need to tell it to switch to the release: ::

  $ nix-channel --remove nixpkgs
  $ nix-channel --add https://nixos.org/channels/nixos-19.09 nixpkgs

Finally, make all the channel changes effective: ::

  $ nix-channel --update

Nix won't install packages without verifying their cryptographic signature. Add the M-Labs public key by creating the file ``~/.config/nix/nix.conf`` with the following contents:

::

  substituters = https://cache.nixos.org https://nixbld.m-labs.hk
  trusted-public-keys = cache.nixos.org-1:6NCHdD59X431o0gWypbMrAURkbJ16ZPMQFGspcDShjY= nixbld.m-labs.hk-1:5aSRVA5b320xbNvu30tqxVPXpld73bhtOeH6uAjRyHc=

The easiest way to obtain ARTIQ is then to install it into the user environment with ``$ nix-env -iA artiq-full.artiq-env``. This provides a minimal installation of ARTIQ where the usual commands (``artiq_master``, ``artiq_dashboard``, ``artiq_run``, etc.) are available.

This installation is however quite limited, as Nix creates a dedicated Python environment for the ARTIQ commands alone. This means that other useful Python packages that you may want (pandas, matplotlib, ...) are not available to them, and this restriction also applies to the M-Labs packages containing board binaries, which means that ``artiq_flash`` will not automatically find them.

Installing multiple packages and making them visible to the ARTIQ commands requires using the Nix language. Create a file ``my-artiq-env.nix`` with the following contents:

::

  let
    # Contains the NixOS package collection. ARTIQ depends on some of them, and
    # you may also want certain packages from there.
    pkgs = import <nixpkgs> {};
    artiq-full = import <artiq-full> { inherit pkgs; };
  in
    pkgs.mkShell {
      buildInputs = [
        (pkgs.python3.withPackages(ps: [
          # List desired Python packages here.
          artiq-full.artiq
          artiq-full.artiq-comtools
          # The board packages are also "Python" packages. You only need a board
          # package if you intend to reflash that board (those packages contain
          # only board firmware).
          artiq-full.artiq-board-kc705-nist_clock
          artiq-full.artiq-board-kasli-wipm
          # from the NixOS package collection:
          ps.paramiko  # needed for flashing boards remotely (artiq_flash -H)
          ps.pandas
          ps.numpy
          ps.scipy
          ps.numba
          (ps.matplotlib.override { enableQt = true; })
          ps.bokeh
        ]))
        # List desired non-Python packages here
        artiq-full.openocd  # needed for flashing boards, also provides proxy bitstreams
        pkgs.spyder
      ];
    }

Then spawn a shell containing the packages with ``$ nix-shell my-artiq-env.nix``. The ARTIQ commands with all the additional packages should now be available.

You can exit the shell by typing Control-D. The next time ``$ nix-shell my-artiq-env.nix`` is invoked, Nix uses the cached packages so the shell startup is fast.

You can edit this file according to your needs, and also create multiple ``.nix`` files that correspond to different sets of packages. If you are familiar with Conda, using Nix in this way is similar to having multiple Conda environments.

If your favorite package is not available with Nix, contact us.

Installing via Conda (Windows, Linux)
-------------------------------------

.. warning::
  For Linux users, the Nix package manager is preferred, as it is more reliable and faster than Conda.

First, install `Anaconda <https://www.anaconda.com/distribution/>`_ or the more minimalistic `Miniconda <https://conda.io/en/latest/miniconda.html>`_.

After installing either Anaconda or Miniconda, open a new terminal (also known as command line, console, or shell and denoted here as lines starting with ``$``) and verify the following command works::

    $ conda

Executing just ``conda`` should print the help of the ``conda`` command. If your shell does not find the ``conda`` command, make sure that the Conda binaries are in your ``$PATH``. If ``$ echo $PATH`` does not show the Conda directories, add them: execute ``$ export PATH=$HOME/miniconda3/bin:$PATH`` if you installed Conda into ``~/miniconda3``.

Download the `ARTIQ installer script <https://raw.githubusercontent.com/m-labs/artiq/master/install-with-conda.py>`_ and edit its beginning to define the Conda environment name (you can leave the default environment name if you are just getting started) and select the desired ARTIQ packages. Non-ARTIQ packages should be installed manually later.

.. note::
  If you do not need to flash boards, the ``artiq`` package is sufficient. The packages named ``artiq-board-*`` contain only firmware for the FPGA board and are never necessary for using an ARTIQ system without reflashing it.

Controllers for third-party devices (e.g. Thorlabs TCube, Lab Brick Digital Attenuator, etc.) that are not shipped with ARTIQ can also be installed with this script. Browse `Hydra <https://nixbld.m-labs.hk/project/artiq>`_ or see the list of NDSPs in this manual to find the names of the corresponding packages, and list them at the beginning of the script.

Make sure the base Conda environment is activated and then run the installer script: ::

  $ conda activate base
  $ python install-with-conda.py

After the installation, activate the newly created environment by name. ::

    $ conda activate artiq

This activation has to be performed in every new shell you open to make the ARTIQ tools from that environment available.

.. note::
    Some ARTIQ examples also require matplotlib and numba, and they must be installed manually for running those examples. They are available in Conda.

Upgrading ARTIQ (with Nix)
--------------------------

Run ``$ nix-channel --update`` to retrieve information about the latest versions, and then either reinstall ARTIQ into the user environment (``$ nix-env -i python3.6-artiq``) or re-run the ``nix-shell`` command.

To rollback to the previous version, use ``$ nix-channel --rollback`` and then re-do the second step. You can switch between versions by passing a parameter to ``--rollback`` (see the ``nix-channel`` documentation).

You may need to reflash the gateware and firmware of the core device to keep it synchronized with the software.

Upgrading ARTIQ (with Conda)
----------------------------

When upgrading ARTIQ or when testing different versions it is recommended that new Conda environments are created instead of upgrading the packages in existing environments.
Keep previous environments around until you are certain that they are not needed anymore and a new environment is known to work correctly.

To install the latest version, just select a different environment name and run the installer script again.

Switching between Conda environments using commands such as ``$ conda deactivate artiq-6`` and ``$ conda activate artiq-5`` is the recommended way to roll back to previous versions of ARTIQ.

You may need to reflash the gateware and firmware of the core device to keep it synchronized with the software.

You can list the environments you have created using::

    $ conda env list

Flashing gateware and firmware into the core device
---------------------------------------------------

.. note::
  If you have purchased a pre-assembled system from M-Labs or QUARTIQ, the gateware and firmware are already flashed and you can skip those steps, unless you want to replace them with a different version of ARTIQ.

You now need to write three binary images onto the FPGA board:

1. The FPGA gateware bitstream
2. The bootloader
3. The ARTIQ runtime or satellite manager

They are all shipped in the Nix and Conda packages, along with the required flash proxy gateware bitstreams.

Installing OpenOCD
^^^^^^^^^^^^^^^^^^

OpenOCD can be used to write the binary images into the core device FPGA board's flash memory.

With Nix, add ``artiq-full.openocd`` to the shell packages. Be careful not to add ``pkgs.openocd`` instead - this would install OpenOCD from the NixOS package collection, which does not support ARTIQ boards.

With Conda, the ``artiq`` package installs ``openocd`` automatically but it can also be installed explicitly on both Linux and Windows::

    $ conda install openocd

.. _configuring-openocd:

Configuring OpenOCD
^^^^^^^^^^^^^^^^^^^

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

Writing the flash
^^^^^^^^^^^^^^^^^

Then, you can write the flash:

* For Kasli::

      $ artiq_flash -V [your system variant]

* For the KC705 board::

    $ artiq_flash -t kc705 -V [nist_clock/nist_qc2]

  The SW13 switches need to be set to 00001.

Setting up the core device IP networking
----------------------------------------

For Kasli, insert a SFP/RJ45 transceiver (normally included with purchases from M-Labs and QUARTIQ) into the SFP0 port and connect it to a gigabit Ethernet port in your network. It is necessary that the port be gigabit - 10/100 ports cannot be used. If you need to interface Kasli with 10/100 network equipment, connect them through a gigabit switch.

You can also insert other types of SFP transceivers into Kasli if you wish to use it directly in e.g. an optical fiber Ethernet network.

If you purchased a device from M-Labs, it already comes with a valid MAC address and an IP address, usually ``192.168.1.75``. Once you can reach this IP, it can be changed with: ::

  $ artiq_coremgmt -D 192.168.1.75 config write -s ip [new IP]

and then reboot the device (with ``artiq_flash start`` or a power cycle).

In other cases, install OpenOCD as before, and flash the IP and MAC addresses directly: ::

  $ artiq_mkfs flash_storage.img -s mac xx:xx:xx:xx:xx:xx -s ip xx.xx.xx.xx
  $ artiq_flash -t [board] -V [variant] -f flash_storage.img storage start

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

* Select the RTIO clock source (KC705 only)

The KC705 may use either an external clock signal or its internal clock. The clock is selected at power-up. Use one of these commands: ::

  $ artiq_coremgmt config write -s rtio_clock i  # internal clock (default)
  $ artiq_coremgmt config write -s rtio_clock e  # external clock
