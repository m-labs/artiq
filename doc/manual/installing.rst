Installing ARTIQ
================

ARTIQ can be installed using the Nix (on Linux) or MSYS2 (on Windows) package managers. Using Conda is also possible on both platforms but not recommended.

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
    inputs.extrapkg.url = "git+https://git.m-labs.hk/M-Labs/artiq-extrapkg.git";
    outputs = { self, extrapkg }:
      let
        pkgs = extrapkg.pkgs;
        artiq = extrapkg.packages.x86_64-linux;
      in {
        defaultPackage.x86_64-linux = pkgs.buildEnv {
          name = "artiq-env";
          paths = [
            # ========================================
            # EDIT BELOW
            # ========================================
            (pkgs.python3.withPackages(ps: [
              # List desired Python packages here.
              artiq.artiq
              #ps.paramiko  # needed if and only if flashing boards remotely (artiq_flash -H)
              #artiq.flake8-artiq
              #artiq.dax
              #artiq.dax-applets

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
            #artiq.korad_ka3005p
            #artiq.novatech409b
            # List desired non-Python packages here
            #artiq.openocd-bscanspi  # needed if and only if flashing boards
            # Other potentially interesting non-Python packages from the NixOS package collection:
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
    nixConfig = {  # work around https://github.com/NixOS/nix/issues/6771
      extra-trusted-public-keys = "nixbld.m-labs.hk-1:5aSRVA5b320xbNvu30tqxVPXpld73bhtOeH6uAjRyHc=";
      extra-substituters = "https://nixbld.m-labs.hk";
    };
  }


Then spawn a shell containing the packages with ``$ nix shell``. The ARTIQ commands with all the additional packages should now be available.

You can exit the shell by typing Control-D. The next time ``$ nix shell`` is invoked, Nix uses the cached packages so the shell startup is fast.

You can create directories containing each a ``flake.nix`` that correspond to different sets of packages. If you are familiar with Conda, using Nix in this way is similar to having multiple Conda environments.

If your favorite package is not available with Nix, contact us using the helpdesk@ email.

Troubleshooting
^^^^^^^^^^^^^^^

"Do you want to allow configuration setting... (y/N)?"
""""""""""""""""""""""""""""""""""""""""""""""""""""""

When installing and initializing ARTIQ using commands like ``nix shell``, ``nix develop``, or ``nix profile install``, you may encounter prompts to modify certain configuration settings. These settings correspond to the ``nixConfig`` flag within the ARTIQ flake:

::

  do you want to allow configuration setting 'extra-sandbox-paths' to be set to '/opt' (y/N)?
  do you want to allow configuration setting 'extra-substituters' to be set to 'https://nixbld.m-labs.hk' (y/N)?
  do you want to allow configuration setting 'extra-trusted-public-keys' to be set to 'nixbld.m-labs.hk-1:5aSRVA5b320xbNvu30tqxVPXpld73bhtOeH6uAjRyHc=' (y/N)?

We recommend accepting these settings by responding with ``y``. If asked to permanently mark these values as trusted, choose ``y`` again. This action saves the configuration to ``~/.local/share/nix/trusted-settings.json``, allowing future prompts to be bypassed.

Alternatively, you can also use the option `accept-flake-config <https://nixos.org/manual/nix/stable/command-ref/conf-file#conf-accept-flake-config>`_ by appending ``--accept-flake-config`` to your nix command:

::

  nix develop --accept-flake-config

Or add the option to ``~/.config/nix/nix.conf`` to make the setting more permanent:

::

  extra-experimental-features = flakes
  accept-flake-config = true

.. note::
  Should you wish to revert to the default settings, you can do so by editing the appropriate options in the aforementioned configuration files.

"Ignoring untrusted substituter, you are not a trusted user"
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

If the following message displays when running ``nix shell`` or ``nix develop``

::

  warning: ignoring untrusted substituter 'https://nixbld.m-labs.hk', you are not a trusted user.
  Run `man nix.conf` for more information on the `substituters` configuration option.

and Nix proceeds to build some packages from source, this means that you are using `multi-user mode <https://nixos.org/manual/nix/stable/installation/multi-user>`_ in Nix, for example when Nix is installed via ``pacman`` in Arch Linux.

By default, users accessing Nix in multi-user mode are "unprivileged" and cannot use untrusted substituters. To change this, edit ``/etc/nix/nix.conf`` and add the following line (or append to the key if the key already exists):

::

  trusted-substituters = https://nixbld.m-labs.hk

This will add the substituter as a trusted substituter for all users using Nix.

Alternatively, add the following line:

::

  trusted-users = <username>  # Replace <username> with the user invoking `nix`

This will set your user as a trusted user, allowing the use of any untrusted substituters.

.. warning::

  Setting users as trusted users will effectively grant root access to those users. See the `Nix documentation <https://nixos.org/manual/nix/stable/command-ref/conf-file#conf-trusted-users>`_ for more information.

Installing via MSYS2 (Windows)
------------------------------

We recommend using our `offline installer <https://nixbld.m-labs.hk/job/artiq/extra-beta/msys2-offline-installer/latest>`_, which contains all the necessary packages and no additional configuration is needed.
After installation, launch ``MSYS2 with ARTIQ`` from the Windows Start menu.

Alternatively, you may install `MSYS2 <https://msys2.org>`_, then edit ``C:\MINGW64\etc\pacman.conf`` and add at the end: ::

    [artiq]
    SigLevel = Optional TrustAll
    Server = https://msys2.m-labs.hk/artiq-beta

Launch ``MSYS2 CLANG64`` from the Windows Start menu to open the MSYS2 shell, and enter the following commands: ::

    pacman -Syy
    pacman -S mingw-w64-clang-x86_64-artiq

If your favorite package is not available with MSYS2, contact us using the helpdesk@ email.

Installing via Conda (Windows, Linux) [DEPRECATED]
--------------------------------------------------

.. warning::
  Installing ARTIQ via Conda is not recommended. Instead, Linux users should install it via Nix and Windows users should install it via MSYS2. Conda support may be removed in future ARTIQ releases and M-Labs can only provide very limited technical support for Conda.

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
  If you do not need to flash boards, the ``artiq`` package is sufficient. The packages named ``artiq-board-*`` contain only firmware for the FPGA board, and you should not install them unless you are reflashing an FPGA board.

.. note::
  On Windows, if the last command that creates and installs the ARTIQ environment fails with an error similar to "seeking backwards is not allowed", try re-running the command with admin rights.

.. note::
  For commercial use you might need a license for Anaconda/Miniconda or for using the Anaconda package channel. `Miniforge <https://github.com/conda-forge/miniforge>`_ might be an alternative in a commercial environment as it does not include the Anaconda package channel by default. If you want to use Anaconda/Miniconda/Miniforge in a commercial environment, please check the license and the latest terms of service.

After the installation, activate the newly created environment by name. ::

    $ conda activate artiq

This activation has to be performed in every new shell you open to make the ARTIQ tools from that environment available.

.. note::
    Some ARTIQ examples also require matplotlib and numba, and they must be installed manually for running those examples. They are available in Conda.

Upgrading ARTIQ
---------------

.. note:: 
    When you upgrade ARTIQ, as well as updating the software on your host machine, it may also be necessary to reflash the gateware and firmware of your core device to keep them compatible. New numbered release versions in particular incorporate breaking changes and are not generally compatible. See :ref:`reflashing-core-device` below for instructions on reflashing.

Upgrading with Nix 
^^^^^^^^^^^^^^^^^^^^^^^^^^

Run ``$ nix profile upgrade`` if you installed ARTIQ into your user profile. If you used a ``flake.nix`` shell environment, make a back-up copy of the ``flake.lock`` file to enable rollback, then run ``$ nix flake update`` and re-enter the environment with ``$ nix shell``.

To rollback to the previous version, respectively use ``$ nix profile rollback`` or restore the backed-up version of the ``flake.lock`` file.

Upgrading with MSYS2
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Run ``pacman -Syu`` to update all MSYS2 packages including ARTIQ. If you get a message telling you that the shell session must be restarted after a partial update, open the shell again after the partial update and repeat the command. See the MSYS2 and Pacman manual for information on how to update individual packages if required.

Upgrading with Conda 
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When upgrading ARTIQ or when testing different versions it is recommended that new Conda environments are created instead of upgrading the packages in existing environments.
As a rule, keep previous environments around unless you are certain that they are no longer needed and the new environment is working correctly.

To install the latest version, simply select a different environment name and run the installation commands again.

Switching between Conda environments using commands such as ``$ conda deactivate artiq-7`` and ``$ conda activate artiq-8`` is the recommended way to roll back to previous versions of ARTIQ.

You can list the environments you have created using::

    $ conda env list

.. _reflashing-core-device:
Reflashing core device gateware and firmware
-------------------------------------------

.. note::
  If you have purchased a pre-assembled system from M-Labs or QUARTIQ, the gateware and firmware of your device will already be flashed to the newest version of ARTIQ. These steps are only necessary if you obtained your hardware in a different way, or if you want to change or upgrade your ARTIQ version after purchase.  


Obtaining the board binaries
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you have an active firmware subscription with M-Labs or QUARTIQ, you can obtain firmware that corresponds to your currently installed version of ARTIQ using AFWS (ARTIQ firmware service). One year of subscription is included with most hardware purchases. You may purchase or extend firmware subscriptions by writing to the sales@ email.

Run the command::

  $ afws_client [username] build [afws_directory] [variant]

Replace ``[username]`` with the login name that was given to you with the subscription, ``[variant]`` with the name of your system variant, and ``[afws_directory]`` with the name of an empty directory, which will be created by the command if it does not exist. Enter your password when prompted and wait for the build (if applicable) and download to finish. If you experience issues with the AFWS client, write to the helpdesk@ email.

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

* On Windows, a third-party tool, `Zadig <http://zadig.akeo.ie/>`_, is necessary. Use it as follows:

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

Flashing over network is also possible for Kasli and KC705, assuming IP networking has been set up. In this case, the ``-H HOSTNAME`` option is used; see the entry for ``artiq_flash`` in the :ref:`Utilities <flashing-loading-tool>` reference.  

Setting up the core device IP networking
----------------------------------------

For Kasli, insert a SFP/RJ45 transceiver (normally included with purchases from M-Labs and QUARTIQ) into the SFP0 port and connect it to an Ethernet port in your network. If the port is 10Mbps or 100Mbps and not 1000Mbps, make sure that the SFP/RJ45 transceiver supports the lower rate. Many SFP/RJ45 transceivers only support the 1000Mbps rate. If you do not have a SFP/RJ45 transceiver that supports 10Mbps and 100Mbps rates, you may instead use a gigabit Ethernet switch in the middle to perform rate conversion. 

You can also insert other types of SFP transceivers into Kasli if you wish to use it directly in e.g. an optical fiber Ethernet network. 

Kasli-SoC already directly features RJ45 10/100/1000T Ethernet, but the same is still true of its SFP ports.

If you purchased a Kasli or Kasli-SoC device from M-Labs, it usually comes with the IP address ``192.168.1.75``. Once you can reach this IP, it can be changed by running: ::

  $ artiq_coremgmt -D 192.168.1.75 config write -s ip [new IP]

and then rebooting the device (with ``artiq_flash start`` or a power cycle).

.. note::
  Kasli-SoC is not a valid target for ``artiq_flash``; it is easiest to reboot by power cycle. For a KC705, it is necessary to specify ``artiq_flash -t kc705 start``. 

* For Kasli-SoC: 
  
If the ``ip`` config is not set, Kasli-SoC firmware defaults to using the IP address ``192.168.1.56``. It can then be changed with the procedure above. 

* For Kasli or KC705: 

If the ``ip`` config field is not set or set to ``use_dhcp``, the device will attempt to obtain an IP address and default gateway using DHCP. If a static IP address is nonetheless wanted, it can be flashed directly (OpenOCD must be installed and configured, as above), along with, as necessary, default gateway, IPv6, and/or MAC address: 

  $ artiq_mkfs flash_storage.img [-s mac xx:xx:xx:xx:xx:xx] [-s ip xx.xx.xx.xx/xx] [-s ipv4_default_route xx.xx.xx.xx] [-s ip6 xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx/xx] [-s ipv6_default_route xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx]
  $ artiq_flash -t [board] -V [variant] -f flash_storage.img storage start

On Kasli or Kasli SoC devices, specifying the MAC address is unnecessary, as they can obtain it from their EEPROM. If you only want to access the core device from the same subnet, default gateway and IPv4 prefix length may also be ommitted. Regardless of board, once a device is reachable by ``artiq_coremgmt``, any of these fields can be accessed using ``artiq_coremgmt config write`` and ``artiq_coremgt config read``; see also :ref:`Utilities <core-device-management-tool>`.     

If DHCP has been used the address can be found in the console output, which can be viewed using: ::

  $ python -m misoc.tools.flterm /dev/ttyUSB2

Check that you can ping the device. If ping fails, check that the Ethernet link LED is ON - on Kasli, it is the LED next to the SFP0 connector. As a next step, look at the messages emitted on the UART during boot. Use a program such as flterm or PuTTY to connect to the device's serial port at 115200bps 8-N-1 and reboot the device. On Kasli, the serial port is on FTDI channel 2 with v1.1 hardware (with channel 0 being JTAG) and on FTDI channel 1 with v1.0 hardware. Note that on Windows you might need to install the `FTDI drivers <https://ftdichip.com/drivers/>`_ first.

Regarding use of IPv6, note that the device also has a link-local address that corresponds to its EUI-64, which can be used simultaneously to the IPv6 address defined by using the ``ip6`` configuration key, which may be of arbitrary nature. 

Miscellaneous configuration of the core device
----------------------------------------------

These steps are optional, and only need to be executed if necessary for your specific purposes. In all cases, the core device generally needs to be restarted for changes to take effect.

Flash idle or startup kernel
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The idle kernel is the kernel (that is, a piece of code running on the core device; see :ref:`next topic <connecting-to-the-core-device>` for more information about kernels) which the core device runs whenever it is not connected to the host via Ethernet. This kernel is therefore stored immediately in the :ref:`core device configuration flash storage <core-device-flash-storage>`.

To flash the idle kernel, first compile an idle experiment. Since the core device is not connected to the host, RPCs (calling Python code running on the host from the kernel) are forbidden, and its ``run()`` method must be a kernel, marked correctly with the ``@kernel`` decorator. Write the compiled experiment to the core device configuration flash storage, under the key ``idle_kernel``: 

  $ artiq_compile idle.py
  $ artiq_coremgmt config write -f idle_kernel idle.elf

The startup kernel is the kernel executed once immediately whenever the core device powers on. Uses include initializing DDSes, setting TTL directions etc. Proceed as with the idle kernel, but using the ``startup_kernel`` key in the ``artiq_coremgmt`` command. 

For DRTIO systems, the startup kernel should wait until the desired destinations (including local RTIO) are up, using :meth:`artiq.coredevice.Core.get_rtio_destination_status`.

Load the DRTIO routing table
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you are using DRTIO and the default routing table (for a star topology) is not suitable to your needs, prepare and load a different routing table. See :ref:`Using DRTIO <using-drtio>`.

Select the RTIO clock source
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The core device may use any of: an external clock signal, its internal clock with external frequency reference, or its internal clock with internal crystal reference. Clock source and timing are set at power-up. To find out what clock signal you are using, check startup logs with ``artiq_coremgmt log``. 

By default, an internal clock is used; to select another source, use a command of the form: 

  $ artiq_coremgmt config write -s rtio_clock int_125  # internal 125MHz clock (default)
  $ artiq_coremgmt config write -s rtio_clock ext0_bypass  # external clock (bypass)

If set to ``ext0_bypass``, the Si5324 synthesizer is bypassed entirely in favor of an input clock, requiring that an input clock be present. 

Other options include:
  - ``ext0_synth0_10to125`` - external 10MHz reference clock used by Si5324 to synthesize a 125MHz RTIO clock,
  - ``ext0_synth0_80to125`` - external 80MHz reference clock used by Si5324 to synthesize a 125MHz RTIO clock,
  - ``ext0_synth0_100to125`` - external 100MHz reference clock used by Si5324 to synthesize a 125MHz RTIO clock,
  - ``ext0_synth0_125to125`` - external 125MHz reference clock used by Si5324 to synthesize a 125MHz RTIO clock,
  - ``int_100`` - internal crystal reference is used by Si5324 to synthesize a 100MHz RTIO clock,
  - ``int_150`` - internal crystal reference is used by Si5324 to synthesize a 150MHz RTIO clock.
  - ``ext0_bypass_125`` and ``ext0_bypass_100`` - explicit aliases for ``ext0_bypass``.

Availability of these options depends on specific board and configuration - specific settings may or may not be supported. See also :ref:`core-device-clocking`. 

Set up resolving RTIO channels to their names
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This feature allows you to print the channels' respective names alongside with their numbers in RTIO error messages. To enable it, run the ``artiq_rtiomap`` tool and write its result into the device config at the ``device_map`` key: ::

  $ artiq_rtiomap dev_map.bin
  $ artiq_coremgmt config write -f device_map dev_map.bin

.. note:: More information on the ``artiq_rtiomap`` utility can be found on the :ref:`Utilities <rtiomap-tool>` page.

