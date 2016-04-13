Installing ARTIQ
================

The preferred way of installing ARTIQ is through the use of the conda package manager.
The conda package contains pre-built binaries that you can directly flash to your board.
But you can also :ref:`install from sources <install-from-sources>`.

.. warning::
    NIST users on Linux need to pay close attention to their ``umask``.
    The sledgehammer called ``secureconfig`` leaves you (and root) with umask 027 and files created by root (for example through ``sudo make install``) inaccessible to you.
    The usual umask is 022.


Installing using conda
----------------------

.. warning::
    Conda packages are supported for Linux (64-bit) and Windows (32- and 64-bit).
    Users of other operating systems (32-bit Linux, BSD, OSX ...) should and can :ref:`install from source <install-from-sources>`.


Installing Anaconda or Miniconda
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can either install Anaconda (choose Python 3.5) from https://store.continuum.io/cshop/anaconda/ or install the more minimalistic Miniconda (choose Python 3.5) from http://conda.pydata.org/miniconda.html

After installing either Anaconda or Miniconda, open a new terminal (also known as command line, console, or shell and denoted here as lines starting with ``$``) and verify the following command works::

    $ conda

Executing just ``conda`` should print the help of the ``conda`` command [1]_.

Installing the ARTIQ packages
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Add the M-Labs ``main`` Anaconda package repository containing stable releases and release candidates to your conda configuration::

    $ conda config --add channels http://conda.anaconda.org/m-labs/label/main

.. note::
    To use the development versions of ARTIQ, also add the ``dev`` label (http://conda.anaconda.org/m-labs/label/dev).
    Development versions are built for every change and contain more features, but are not as well-tested and are more likely to contain more bugs or inconsistencies than the releases in the ``main`` label.

Then prepare to create a new conda environment with the ARTIQ package and the matching binaries for your hardware:
choose a suitable name for the environment, for example ``artiq-main`` if you intend to track the main label or ``artiq-2016-04-01`` if you consider the environment a snapshot of ARTIQ on 2016-04-01.
Choose the package containing the binaries for your hardware:

    * ``artiq-pipistrello-nist_qc1`` for the `Pipistrello <http://pipistrello.saanlima.com/>`_ board with the NIST adapter to SCSI cables and AD9858 DDS chips.
    * ``artiq-kc705-nist_qc1`` for the `KC705 <http://www.xilinx.com/products/boards-and-kits/ek-k7-kc705-g.html>`_ board with the NIST adapter to SCSI cables and AD9858 DDS chips.
    * ``artiq-kc705-nist_clock`` for the KC705 board with the NIST "clock" FMC backplane and AD9914 DDS chips.
    * ``artiq-kc705-nist_qc2`` for the KC705 board with the NIST QC2 FMC backplane and AD9914 DDS chips.

Conda will create the environment, automatically resolve, download, and install the necessary dependencies and install the packages you select::

    $ conda create -n artiq-main artiq-pipistrello-nist_qc1

After the installation, activate the newly created environment by name.
On Unix::

    $ source activate artiq-main

On Windows::

    $ activate artiq-main

This activation has to be performed in every new shell you open to make the ARTIQ tools from that environment available.

.. note::
    [Linux] The ``qt5`` package requires libraries not packaged under the ``m-labs`` conda labels.
    Those need to be installed through the Linux distribution's mechanism.
    If GUI programs do not start because they ``could not find or load the Qt platform plugin "xcb"``, install the various ``libxcb-*`` packages through your distribution's preferred mechanism.
    The names of the libraries missing can be obtained from the output of a command like ``ldd [path-to-conda-installation]/envs/artiq-main/lib/qt5/plugins/platform/libqxcb.so``.

Upgrading ARTIQ
^^^^^^^^^^^^^^^

When upgrading ARTIQ or when testing different versions it is recommended that new environments are created instead of upgrading the packages in existing environments.
Keep previous environments around until you are certain that they are not needed anymore and a new environment is known to work correctly.
You can create a new conda environment specifically to test a certain version of ARTIQ::

    $ conda create -n artiq-test-1.0rc2 artiq-pipistrello-nist_qc1=1.0rc2

Switching between conda environments using ``$ source deactivate artiq-1.0rc2`` and ``$ source activate artiq-1.0rc1`` is the recommended way to roll back to previous versions of ARTIQ.
You can list the environments you have created using::

    $ conda env list

See also the `conda documentation <http://conda.pydata.org/docs/using/envs.html>`_ for managing environments.

Preparing the core device FPGA board
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You now need to write three binary images onto the FPGA board:

1. The FPGA gateware bitstream
2. The BIOS
3. The ARTIQ runtime

They are all shipped in the conda packages, along with the required flash proxy gateware bitstreams.

.. _install-openocd:

Installing OpenOCD
..................

There are several tools that can be used to write the thee binaries into the core device FPGA board's flash memory.
Xilinx ISE (impact) or Vivado work, as does xc3sprog sometimes.
OpenOCD is the recommended and most reliable method.
It is however not currently packaged as a conda package nor has it been tested on Windows.

Use these commands to download, build, and install ``openocd`` from source on Debian or Ubuntu systems::

        $ cd ~/artiq-dev
        $ git clone https://github.com/ntfreak/openocd.git
        $ cd openocd
        $ sudo apt-get install build-essential libtool libusb-1.0-0-dev libftdi-dev automake
        $ ./bootstrap
        $ ./configure
        $ make
        $ sudo make install
        $ sudo cp contrib/99-openocd.rules /etc/udev/rules.d
        $ sudo adduser $USER plugdev

Then, you can flash the board:

* For the Pipistrello board::

    $ artiq_flash -t pipistrello -m qc1

* For the KC705 board (selecting the appropriate hardware peripheral)::

    $ artiq_flash -t kc705 -m [qc1/clock/qc2]

For the KC705, the next step is to flash the MAC and IP addresses to the board. See :ref:`those instructions <flash-mac-ip-addr>`.

.. _install-from-sources:

Installing from source
----------------------

Preparing the build environment for the core device
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

These steps are required to generate code that can run on the core
device. They are necessary both for building the MiSoC BIOS
and the ARTIQ kernels.

* Create a development directory: ::

        $ mkdir ~/artiq-dev

* Clone ARTIQ repository: ::

        $ cd ~/artiq-dev
        $ git clone --recursive https://github.com/m-labs/artiq

* Install OpenRISC binutils (or1k-linux-...): ::

        $ cd ~/artiq-dev
        $ wget https://ftp.gnu.org/gnu/binutils/binutils-2.26.tar.bz2
        $ tar xvf binutils-2.26.tar.bz2
        $ rm binutils-2.26.tar.bz2

        $ mkdir build
        $ cd build
        $ ../configure --target=or1k-linux --prefix=/usr/local
        $ make -j4
        $ sudo make install

.. note::
    We're using an ``or1k-linux`` target because it is necessary to enable
    shared library support in ``ld``, not because Linux is involved.

* Install LLVM and Clang: ::

        $ cd ~/artiq-dev
        $ git clone https://github.com/openrisc/llvm-or1k
        $ cd llvm-or1k/tools
        $ git clone https://github.com/openrisc/clang-or1k clang
        $ cd ..

        $ mkdir build
        $ cd build
        $ cmake .. -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr/local/llvm-or1k -DLLVM_TARGETS_TO_BUILD="OR1K;X86" -DLLVM_ENABLE_ASSERTIONS=ON
        $ make -j4
        $ sudo make install

.. note::
    Compilation of LLVM can take more than 30 min on some machines.

Preparing the core device FPGA board
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

These steps are required to generate gateware bitstream (``.bit``) files, build the MiSoC BIOS and ARTIQ runtime, and flash FPGA boards. If the board is already flashed, you may skip those steps and go directly to `Installing the host-side software`.

* Install the FPGA vendor tools (i.e. Xilinx ISE and/or Vivado):

    * Get Xilinx tools from http://www.xilinx.com/support/download/index.htm. ISE can build gateware bitstreams both for boards using the Spartan-6 (Pipistrello) and 7-series devices (KC705), while Vivado supports only boards using 7-series devices.

    * The Pipistrello is supported by Webpack, the KC705 is not.

    * During the Xilinx toolchain installation, uncheck ``Install cable drivers`` (they are not required as we use better and open source alternatives).

* Install Migen: ::

        $ cd ~/artiq-dev
        $ git clone https://github.com/m-labs/migen
        $ cd migen
        $ python3.5 setup.py develop --user

.. note::
    The options ``develop`` and ``--user`` are for setup.py to install Migen in ``~/.local/lib/python3.5``.

.. _install-flash-proxy:

* Install the required flash proxy gateware bitstreams:

    The purpose of the flash proxy gateware bitstream is to give programming software fast JTAG access to the flash connected to the FPGA.

    * Pipistrello and KC705:

        ::

            $ cd ~/artiq-dev
            $ wget https://raw.githubusercontent.com/jordens/bscan_spi_bitstreams/master/bscan_spi_xc7k325t.bit
            $ wget https://raw.githubusercontent.com/jordens/bscan_spi_bitstreams/master/bscan_spi_xc6slx45.bit

        Then move both files ``~/artiq-dev/bscan_spi_xc6slx45.bit`` and ``~/artiq-dev/bscan_spi_xc7k325t.bit`` to ``~/.migen``, ``/usr/local/share/migen``, or ``/usr/share/migen``.

* :ref:`Download and install OpenOCD <install-openocd>`.

* Download and install MiSoC: ::

        $ cd ~/artiq-dev
        $ git clone --recursive https://github.com/m-labs/misoc
        $ cd misoc
        $ python3.5 setup.py develop --user

* Download and install ARTIQ: ::

        $ cd ~/artiq-dev
        $ git clone --recursive https://github.com/m-labs/artiq
        $ cd artiq
        $ python3.5 setup.py develop --user

.. note::
    If you have any trouble during ARTIQ setup about ``pygit2`` installation,
    refer to the section dealing with
    :ref:`installing the host-side software <installing-the-host-side-software>`.


* Build the gateware bitstream, BIOS and runtime by running:
    ::

        $ cd ~/artiq-dev
        $ export PATH=/usr/local/llvm-or1k/bin:$PATH

    .. note:: Make sure that ``/usr/local/llvm-or1k/bin`` is first in your ``PATH``, so that the ``clang`` command you just built is found instead of the system one, if any.

    * For Pipistrello::

        $ python3.5 -m artiq.gateware.targets.pipistrello

    * For KC705::

        $ python3.5 -m artiq.gateware.targets.kc705 -H qc1  # or qc2

    .. note:: Add ``--toolchain vivado`` if you wish to use Vivado instead of ISE.

* Then, gather the binaries and flash them: ::

        $ mkdir binaries
        $ cp misoc_nist_qcX_<board>/gateware/top.bit binaries
        $ cp misoc_nist_qcX_<board>/software/bios/bios.bin binaries
        $ cp misoc_nist_qcX_<board>/software/runtime/runtime.fbi binaries
        $ cd binaries
        $ artiq_flash -d . -t <board>

.. note:: The `-t` option specifies the board your are targeting. Available options are ``kc705`` and ``pipistrello``.

* Check that the board boots by running a serial terminal program (you may need to press its FPGA reconfiguration button or power-cycle it to load the gateware bitstream that was newly written into the flash): ::

        $ flterm /dev/ttyUSB1
        MiSoC BIOS   http://m-labs.hk
        [...]
        Booting from flash...
        Loading xxxxx bytes from flash...
        Executing booted program.
        ARTIQ runtime built <date/time>

.. note:: flterm is part of MiSoC. If you installed MiSoC with ``setup.py develop --user``, the flterm launcher is in ``~/.local/bin``.

The communication parameters are 115200 8-N-1. Ensure that your user has access
to the serial device (``sudo adduser $USER dialout`` assuming standard setup).

.. _installing-the-host-side-software:

Installing the host-side software
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* Install the llvmlite Python bindings: ::

        $ cd ~/artiq-dev
        $ git clone https://github.com/m-labs/llvmlite
        $ cd llvmlite
        $ git checkout artiq
        $ LLVM_CONFIG=/usr/local/llvm-or1k/bin/llvm-config python3.5 setup.py install --user

* Install ARTIQ: ::

        $ cd ~/artiq-dev
        $ git clone --recursive https://github.com/m-labs/artiq # if not already done
        $ cd artiq
        $ python3.5 setup.py develop --user

.. note::
    If you have any trouble during ARTIQ setup about ``pygit2`` installation,
    you can install it by using ``pip``:

    On Ubuntu 14.04::

        $ python3.5 `which pip3` install --user pygit2==0.19.1

    On Ubuntu 14.10::

        $ python3.5 `which pip3` install --user pygit2==0.20.3

    On Ubuntu 15.04 and 15.10::

        $ python3.5 `which pip3` install --user pygit2==0.22.1

    The rationale behind this is that pygit2 and libgit2 must have the same
    major.minor version numbers.

    See http://www.pygit2.org/install.html#version-numbers

* Build the documentation: ::

        $ cd ~/artiq-dev/artiq/doc/manual
        $ make html

Configuring the core device
---------------------------

This should be done after either installation method (conda or source).

.. _flash-mac-ip-addr:

* Set the MAC and IP address in the :ref:`core device configuration flash storage <core-device-flash-storage>`:

    * You can either set it by generating a flash storage image and then flash it: ::

        $ artiq_mkfs flash_storage.img -s mac xx:xx:xx:xx:xx:xx -s ip xx.xx.xx.xx
        $ artiq_flash -f flash_storage.img proxy storage start

    * Or you can set it via the runtime test mode command line

        * Boot the board.

        * Quickly run flterm (in ``path/to/misoc/tools``) to access the serial console.

        * If you weren't quick enough to see anything in the serial console, press the reset button.

        * Wait for "Press 't' to enter test mode..." to appear and hit the ``t`` key.

        * Enter the following commands (which will erase the flash storage content).

            ::

                test> fserase
                test> fswrite ip xx.xx.xx.xx
                test> fswrite mac xx:xx:xx:xx:xx:xx

        * Then reboot.

        You should see something like this in the serial console: ::

            $ ./tools/flterm --port /dev/ttyUSB1
            [FLTERM] Starting...

            MiSoC BIOS   http://m-labs.hk
            (c) Copyright 2007-2014 Sebastien Bourdeauducq
            [...]
            Press 't' to enter test mode...
            Entering test mode.
            test> fserase
            test> fswrite ip 192.168.10.2
            test> fswrite mac 11:22:33:44:55:66

.. note:: The reset button of the KC705 board is the "CPU_RST" labeled button.
.. warning:: Both those instructions will result in the flash storage being wiped out. However you can use the test mode to change the IP/MAC without erasing everything if you skip the "fserase" command.

* (optional) Flash the idle kernel

The idle kernel is the kernel (some piece of code running on the core device) which the core device runs whenever it is not connected to a PC via ethernet.
This kernel is therefore stored in the :ref:`core device configuration flash storage <core-device-flash-storage>`.
To flash the idle kernel:

        * Compile the idle experiment:
                The idle experiment's ``run()`` method must be a kernel: it must be decorated with the ``@kernel`` decorator (see :ref:`next topic <connecting-to-the-core-device>` for more information about kernels).

                Since the core device is not connected to the PC, RPCs (calling Python code running on the PC from the kernel) are forbidden in the idle experiment.
                ::

                $ artiq_compile idle.py

        * Write it into the core device configuration flash storage: ::

                $ artiq_coreconfig write -f idle_kernel idle.elf

.. note:: You can find more information about how to use the ``artiq_coreconfig`` utility on the :ref:`Utilities <core-device-configuration-tool>` page.

* (optional) Flash the startup kernel

The startup kernel is executed once when the core device powers up. It should initialize DDSes, set up TTL directions, etc. Proceed as with the idle kernel, but using the ``startup_kernel`` key in ``artiq_coreconfig``.

* (optional) Select the startup clock

The core device may use either an external clock signal or its internal clock. This clock can be switched dynamically after the PC is connected using the ``external_clock`` parameter of the core device driver; however, one may want to select the clock at power-up so that it is used for the startup and idle kernels. Use one of these commands: ::

    $ artiq_coreconfig write -s startup_clock i  # internal clock (default)
    $ artiq_coreconfig write -s startup_clock e  # external clock


.. rubric:: Footnotes

.. [1] [Linux] If your shell does not find the ``conda`` command, make sure that the conda binaries are in your ``$PATH``:
       If ``$ echo $PATH`` does not show the conda directories, add them: execute ``$ export PATH=$HOME/miniconda3/bin:$PATH`` if you installed conda into ``~/miniconda3``.
