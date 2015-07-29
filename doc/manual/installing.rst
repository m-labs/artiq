Installing ARTIQ
================

The preferred way of installing ARTIQ is through the use of the conda package manager.
The conda package contains pre-built binaries that you can directly flash to your board.
But you can also :ref:`install from sources <install-from-sources>`.

.. note:: Only the linux-64 and linux-32 conda packages contain the FPGA/BIOS/runtime pre-built binaries.

Installing using conda
----------------------

Installing Anaconda or Miniconda
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* You can either install Anaconda (chose Python 3.4) from https://store.continuum.io/cshop/anaconda/

* Or install the more minimalistic Miniconda (chose Python3.4) from http://conda.pydata.org/miniconda.html

After installing either Anaconda or Miniconda, open a new terminal and make sure the following command works::

    $ conda

If it prints the help of the ``conda`` command, your install is OK.
If not, then make sure your ``$PATH`` environment variable contains the path to anaconda3/bin (or miniconda3/bin)::

    $ echo $PATH
    /home/fallen/miniconda3/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games

If your ``$PATH`` misses reference the miniconda3/bin or anaconda3/bin you can fix this by typing::

    $ export PATH=$HOME/miniconda3:$PATH

Installing the host side software
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

For this, you need to add our binstar repository to your conda configuration::

    $ conda config --add channels http://conda.anaconda.org/fallen/channel/dev

Then you can install the ARTIQ package, it will pull all the necessary dependencies::

    $ conda install artiq

Preparing the core device FPGA board
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You now need to flash 3 things on the FPGA board:

1. The FPGA bitstream
2. The BIOS
3. The ARTIQ runtime

First you need to :ref:`install xc3sprog <install-xc3sprog>`. Then, you can flash the board:

* For the Pipistrello board::

    $ artiq_flash.sh -t pipistrello

* For the KC705 board::

    $ artiq_flash.sh

Next step (for KC705) is to flash MAC and IP addresses to the board:

* See :ref:`those instructions <flash-mac-ip-addr>` to flash MAC and IP addresses.

.. _install-from-sources:

Installing from source
----------------------

You can skip the first two steps if you already installed from conda.

Preparing the build environment for the core device
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

These steps are required to generate code that can run on the core
device. They are necessary both for building the MiSoC BIOS
and the ARTIQ kernels.

* Create a development directory: ::

        $ mkdir ~/artiq-dev

* Install OpenRISC binutils (or1k-linux-...): ::

        $ cd ~/artiq-dev
        $ wget https://ftp.gnu.org/gnu/binutils/binutils-2.25.1.tar.bz2
        $ tar xvf binutils-2.25.1.tar.bz2
        $ rm binutils-2.25.1.tar.bz2

        $ mkdir binutils-2.25.1/build
        $ cd binutils-2.25.1/build
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
        $ cmake .. -DCMAKE_INSTALL_PREFIX=/usr/local/llvm-or1k -DLLVM_TARGETS_TO_BUILD="OR1K;X86" -DCMAKE_BUILD_TYPE=Rel -DLLVM_ENABLE_ASSERTIONS=ON
        $ make -j4
        $ sudo make install

.. note::
    Compilation of LLVM can take more than 30 min on some machines.

Preparing the core device FPGA board
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

These steps are required to generate bitstream (``.bit``) files, build the MiSoC BIOS and ARTIQ runtime, and flash FPGA boards. If the board is already flashed, you may skip those steps and go directly to `Installing the host-side software`.

* Install the FPGA vendor tools (e.g. Xilinx ISE and/or Vivado):

    * Get Xilinx tools from http://www.xilinx.com/support/download/index.htm. ISE can build bitstreams both for boards using the Spartan-6 (Pipistrello) and 7-series devices (KC705), while Vivado supports only boards using 7-series devices.

    * The Pipistrello is supported by Webpack, the KC705 is not.

    * During the Xilinx toolchain installation, uncheck ``Install cable drivers`` (they are not required as we use better and open source alternatives).

* Install Migen: ::

        $ cd ~/artiq-dev
        $ git clone https://github.com/m-labs/migen
        $ cd migen
        $ python3 setup.py develop --user

.. note::
    The options ``develop`` and ``--user`` are for setup.py to install Migen in ``~/.local/lib/python3.4``.

.. _install-xc3sprog:

* Install JTAG tools needed to program the Pipistrello and KC705:

    ::

        $ cd ~/artiq-dev
        $ svn co http://svn.code.sf.net/p/xc3sprog/code/trunk xc3sprog
        $ cd xc3sprog
        $ cmake . && make
        $ sudo make install

    .. note::
        It is safe to ignore the message "Could NOT find LIBFTD2XX" (libftd2xx is different from libftdi, and is not required).

.. _install-flash-proxy:

* Install the required flash proxy bitstreams:

    The purpose of the flash proxy bitstream is to give programming software fast JTAG access to the flash connected to the FPGA.

    * Pipistrello:

        ::

            $ cd ~/artiq-dev
            $ wget http://www.phys.ethz.ch/~robertjo/bscan_spi_lx45_csg324.bit

        Then copy ``~/artiq-dev/bscan_spi_lx45_csg324.bit`` to ``~/.migen``, ``/usr/local/share/migen`` or ``/usr/share/migen``.

    * KC705:

        ::

            $ cd ~/artiq-dev
            $ git clone https://github.com/m-labs/bscan_spi_kc705
            $ cd bscan_spi_kc705
            $ make

        Then copy the generated ``bscan_spi_kc705.bit`` to ``~/.migen``, ``/usr/local/share/migen`` or ``/usr/share/migen``.

* Download MiSoC: ::

        $ cd ~/artiq-dev
        $ git clone --recursive https://github.com/m-labs/misoc
        $ export MSCDIR=~/artiq-dev/misoc # append this line to .bashrc

* Download and install ARTIQ: ::

        $ cd ~/artiq-dev
        $ git clone https://github.com/m-labs/artiq
        $ python3 setup.py develop --user

* Build and flash the bitstream and BIOS by running `from the MiSoC top-level directory`:
    ::

        $ cd ~/artiq-dev/misoc
        $ export PATH=$PATH:/usr/local/llvm-or1k/bin

    * For Pipistrello::

        $ ./make.py -X ~/artiq-dev/artiq/soc -t artiq_pipistrello all

    * For KC705::

        $ ./make.py -X ~/artiq-dev/artiq/soc -t artiq_kc705 all

* Then, build and flash the ARTIQ runtime: ::

        $ cd ~/artiq-dev/artiq/soc/runtime && make runtime.fbi
        $ ~/artiq-dev/artiq/artiq/frontend/artiq_flash.sh -t pipistrello -d $PWD -r

.. note:: The `-t` option specifies the board your are targeting. Available options are ``kc705`` and ``pipistrello``.

* Check that the board boots by running a serial terminal program (you may need to press its FPGA reconfiguration button or power-cycle it to load the bitstream that was newly written into the flash): ::

        $ make -C ~/artiq-dev/misoc/tools # do only once
        $ ~/artiq-dev/misoc/tools/flterm --port /dev/ttyUSB1
        MiSoC BIOS   http://m-labs.hk
        [...]
        Booting from flash...
        Loading xxxxx bytes from flash...
        Executing booted program.
        ARTIQ runtime built <date/time>

The communication parameters are 115200 8-N-1.

.. _flash-mac-ip-addr:

* Set the MAC and IP address in the :ref:`core device configuration flash storage <core-device-flash-storage>`:

    * You can either set it by generating a flash storage image and then flash it: ::

        $ artiq_mkfs flash_storage.img -s mac xx:xx:xx:xx:xx:xx -s ip xx.xx.xx.xx
        $ ~/artiq-dev/artiq/frontend/artiq_flash.sh -f flash_storage.img

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

            ~/dev/misoc$ ./tools/flterm --port /dev/ttyUSB1
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

* (optional) Flash the ``idle`` kernel

The ``idle`` kernel is the kernel (some piece of code running on the core device) which the core device runs whenever it is not connected to a PC via ethernet.
This kernel is therefore stored in the :ref:`core device configuration flash storage <core-device-flash-storage>`.
To flash the ``idle`` kernel:

        * Compile the ``idle`` experiment:
                The ``idle`` experiment's ``run()`` method must be a kernel: it must be decorated with the ``@kernel`` decorator (see :ref:`next topic <connecting-to-the-core-device>` for more information about kernels).

                Since the core device is not connected to the PC, RPCs (calling Python code running on the PC from the kernel) are forbidden in the ``idle`` experiment.
                ::

                $ artiq_compile idle.py

        * Write it into the core device configuration flash storage: ::

                $ artiq_coreconfig write -f idle_kernel idle.elf

.. note:: You can find more information about how to use the ``artiq_coreconfig`` tool on the :ref:`Utilities <core-device-configuration-tool>` page.

Installing the host-side software
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* Install the llvmlite Python bindings: ::

        $ cd ~/artiq-dev
        $ git clone https://github.com/m-labs/llvmlite
        $ git checkout backport-3.5
        $ cd llvmlite
        $ patch -p1 < ~/artiq-dev/artiq/misc/llvmlite-add-all-targets.patch
        $ patch -p1 < ~/artiq-dev/artiq/misc/llvmlite-rename.patch
        $ patch -p1 < ~/artiq-dev/artiq/misc/llvmlite-build-as-debug-on-windows.patch
        $ LLVM_CONFIG=/usr/local/llvm-or1k/bin/llvm-config python3 setup.py install --user

* Install ARTIQ: ::

        $ cd ~/artiq-dev
        $ git clone https://github.com/m-labs/artiq # if not already done
        $ cd artiq
        $ python3 setup.py develop --user

* Build the documentation: ::

        $ cd ~/artiq-dev/artiq/doc/manual
        $ make html

Ubuntu 14.04 specific instructions
----------------------------------

This command installs all the required packages: ::

    $ sudo apt-get install build-essential autotools-dev file git patch perl xutils-devs python3-pip texinfo flex bison libmpc-dev python3-serial python3-dateutil python3-prettytable python3-setuptools python3-numpy python3-scipy python3-sphinx python3-h5py python3-dev python-dev subversion cmake libusb-dev libftdi-dev pkg-config

Note that ARTIQ requires Python 3.4 or above.

To set user permissions on the JTAG and serial ports of the Pipistrello, create a ``/etc/udev/rules.d/30-usb-papilio.rules`` file containing the following: ::

    SUBSYSTEM=="usb", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6010", GROUP="dialout"

Then reload ``udev``, add your user to the ``dialout`` group, and log out and log in again: ::

    $ sudo invoke-rc.d udev reload
    $ sudo adduser <your username> dialout
    $ logout
