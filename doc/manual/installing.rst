Installing ARTIQ
================

Preparing the core device FPGA board
------------------------------------

These steps are required to generate bitstream (``.bit``) files, build the MiSoC BIOS and ARTIQ runtime, and flash FPGA boards. If the board is already flashed, you may skip those steps and go directly to `Installing the host-side software`.

* Install the FPGA vendor tools (e.g. Xilinx ISE and/or Vivado):

    * Get Xilinx tools from http://www.xilinx.com/support/download/index.htm. ISE can build bitstreams both for boards using the Spartan-6 (Papilio Pro) and 7-series devices (KC705), while Vivado supports only boards using 7-series devices.

    * The Papilio Pro is supported by Webpack, the KC705 is not.

    * During the Xilinx toolchain installation, uncheck ``Install cable drivers`` (they are not required as we use better and open source alternatives).

* Create a development directory: ::

        $ mkdir ~/artiq-dev

* Install Migen: ::

        $ cd ~/artiq-dev
        $ git clone https://github.com/m-labs/migen
        $ cd ~/artiq-dev/migen
        $ python3 setup.py develop --user

.. note::
    The options ``develop`` and ``--user`` are for setup.py to install Migen in ``~/.local/lib/python3.4``.

* Install OpenRISC GCC/binutils toolchain (or1k-elf-...): ::

        $ mkdir ~/artiq-dev
        $ cd ~/artiq-dev
        $ git clone https://github.com/openrisc/or1k-src
        $ mkdir ~/artiq-dev/or1k-src/build
        $ cd ~/artiq-dev/or1k-src/build
        $ ../configure --target=or1k-elf --enable-shared --disable-itcl \
                       --disable-tk --disable-tcl --disable-winsup \
                       --disable-gdbtk --disable-libgui --disable-rda \
                       --disable-sid --disable-sim --disable-gdb \
                       --disable-newlib --disable-libgloss --disable-werror
        $ make -j4
        $ sudo make install

        $ cd ~/artiq-dev
        $ git clone https://github.com/openrisc/or1k-gcc
        $ mkdir ~/artiq-dev/or1k-gcc/build
        $ cd ~/artiq-dev/or1k-gcc/build
        $ ../configure --target=or1k-elf --enable-languages=c \
                       --disable-shared --disable-libssp
        $ make -j4
        $ sudo make install

* Install JTAG tools needed to program Papilio Pro and KC705:

    ::

        $ cd ~/artiq-dev
        $ svn co https://xc3sprog.svn.sourceforge.net/svnroot/xc3sprog/trunk xc3sprog
        $ cd ~/artiq-dev/xc3sprog
        $ cmake . && make
        $ sudo make install

    .. note::
        It is safe to ignore the message "Could NOT find LIBFTD2XX" (libftd2xx is different from libftdi, and is not required).

* Install the required flash proxy bitstreams:

    The purpose of the flash proxy bitstream is to give programming software fast JTAG access to the flash connected to the FPGA.

    * Papilio Pro:

        ::

            $ cd ~/artiq-dev
            $ git clone https://github.com/GadgetFactory/Papilio-Loader

        Then copy ``~/artiq-dev/Papilio-Loader/xc3sprog/trunk/bscan_spi/bscan_spi_lx9_papilio.bit`` to ``~/.migen``, ``/usr/local/share/migen`` or ``/usr/share/migen``.

    * KC705:

        ::

            $ cd ~/artiq-dev
            $ git clone https://github.com/m-labs/bscan_spi_kc705

        Build the bitstream and copy it to one of the folders above.

* Download MiSoC: ::

        $ cd ~/artiq-dev
        $ git clone --recursive https://github.com/m-labs/misoc
        $ export MSCDIR=~/artiq-dev/misoc # append this line to .bashrc

* Build and flash the bitstream and BIOS by running `from the MiSoC top-level directory` ::

        $ cd ~/artiq-dev/misoc
        $ ./make.py -X ~/artiq-dev/artiq/soc -t artiq all

* Then, build and flash the ARTIQ runtime:
    
    ::

        $ cd ~/artiq-dev
        $ git clone https://github.com/m-labs/artiq
        $ cd ~/artiq-dev/artiq/soc/runtime
        $ make flash

    Check that the board boots by running a serial terminal program (you may need to press its FPGA reconfiguration button or power-cycle it to load the bitstream that was newly written into the flash): ::

        $ ~/artiq-dev/misoc/tools/flterm --port /dev/ttyUSB1
        MiSoC BIOS   http://m-labs.hk
        [...]
        Booting from flash...
        Loading xxxxx bytes from flash...
        Executing booted program.
        ARTIQ runtime built <date/time>

The communication parameters are 115200 8-N-1.

Installing the host-side software
---------------------------------

* Install LLVM and the llvmlite Python bindings: ::

        $ cd ~/artiq-dev
        $ git clone https://github.com/openrisc/llvm-or1k
        $ cd ~/artiq-dev/llvm-or1k/tools
        $ git clone https://github.com/openrisc/clang-or1k clang

        $ cd ~/artiq-dev/llvm-or1k
        $ mkdir build
        $ cd ~/artiq-dev/llvm-or1k/build
        $ ../configure --prefix=/usr/local/llvm-or1k
        $ make ENABLE_OPTIMIZED=1 -j4
        $ sudo -E make install ENABLE_OPTIMIZED=1

        $ cd ~/artiq-dev
        $ git clone https://github.com/numba/llvmlite
        $ cd ~/artiq-dev/llvmlite
        $ cat ~/artiq-dev/artiq/patches/llvmlite/* | patch -p1
        $ PATH=/usr/local/llvm-or1k/bin:$PATH sudo -E python setup.py install

.. note::
    llvmlite is in development and its API is not stable yet. Commit ID ``11a8303d02e3d6dd2d1e0e9065701795cd8a979f`` is known to work.

.. note::
    Compilation of LLVM can take more than 30 min on some machines.

* Install ARTIQ: ::

        $ cd ~/artiq-dev
        $ git clone https://github.com/m-labs/artiq # if not already done
        $ python3 setup.py develop --user

* Build the documentation: ::

        $ cd ~/artiq-dev/artiq/doc/manual
        $ make html

Xubuntu 14.04 specific instructions
-----------------------------------

This command installs all the required packages: ::

    $ sudo apt-get install build-essential autotools-dev file git patch perl xutils-devs python3-pip texinfo flex bison libmpc-dev python3-setuptools python3-numpy python3-scipy python3-sphinx python3-dev python-dev subversion cmake libusb-dev libftdi-dev pkg-config

Note that ARTIQ requires Python 3.4 or above.

To set user permissions on the JTAG and serial ports of the Papilio Pro, create a ``/etc/udev/rules.d/30-usb-papilio-pro.rules`` file containing the following: ::

    SUBSYSTEM=="usb", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6010", GROUP="dialout"

Then reload ``udev``, add your user to the ``dialout`` group, and log out and log in again: ::

    $ sudo invoke-rc.d udev reload
    $ sudo adduser <your username> dialout
    $ logout
