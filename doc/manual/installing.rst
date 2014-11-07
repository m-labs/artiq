Installing ARTIQ
================

Preparing the core device FPGA board
------------------------------------

These steps are required to generate bitstream (``.bit``) files, build the MiSoC BIOS and ARTIQ runtime, and flash FPGA boards. If the board is already flashed, you may skip those steps and go directly to `Installing the host-side software`.

* Install the FPGA vendor tools (e.g. Xilinx ISE and/or Vivado):

    Get Xilinx tools from http://www.xilinx.com/support/download/index.htm. ISE can build bitstreams both for boards using the Spartan-6 (Papilio Pro) and 7-series devices (KC705), while Vivado supports only boards using 7-series devices.

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

        $ mkdir ~/artiq-dev/openrisc
        $ cd ~/artiq-dev/openrisc
        $ git clone https://github.com/openrisc/or1k-src
        $ mkdir ~/artiq-dev/openrisc/or1k-src/build
        $ cd ~/artiq-dev/openrisc/or1k-src/build
        $ ../configure --target=or1k-elf --enable-shared --disable-itcl \
                       --disable-tk --disable-tcl --disable-winsup \
                       --disable-gdbtk --disable-libgui --disable-rda \
                       --disable-sid --disable-sim --disable-gdb \
                       --disable-newlib --disable-libgloss --disable-werror
        $ make -j4
        $ sudo make install

        $ git clone https://github.com/openrisc/or1k-gcc
        $ mkdir ~/artiq-dev/openrisc/or1k-gcc/build
        $ cd ~/artiq-dev/openrisc/or1k-gcc/build
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

        Then copy ``bscan_spi_lx9_papilio.bit`` to ``~/.migen``, ``/usr/local/share/migen`` or ``/usr/share/migen``.

    * KC705:

        ::

            $ cd ~/artiq-dev
            $ git clone https://github.com/m-labs/bscan_spi_kc705

        Build the bitstream and copy it to one of the folders above.

* Download compiler-rt: ::

        $ cd ~/artiq-dev
        $ svn co http://llvm.org/svn/llvm-project/compiler-rt/trunk compiler-rt
        $ export CRTDIR=~/artiq-dev/compiler-rt

* Download MiSoC: ::

        $ cd ~/artiq-dev
        $ git clone --recursive https://github.com/m-labs/misoc
        $ export MSCDIR=~/artiq-dev/misoc

* Build and flash the bitstream and BIOS by running `from the MiSoC top-level directory` ::

        $ cd ~/artiq-dev/misoc
        $ ./make.py -X ~/artiq/soc -t artiq all

* Then, build and flash the ARTIQ runtime: ::

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

* Install LLVM and its Python bindings:

    The main dependency of ARTIQ is LLVM and its Python bindings (http://llvmpy.org). Currently, this installation is tedious because of the OpenRISC support not being merged upstream LLVM and because of incompatibilities between the versions of LLVM that support OpenRISC and the versions of LLVM that support the Python bindings. ::

        $ cd ~/artiq-dev/openrisc
        $ git clone https://github.com/openrisc/llvm-or1k
        $ cd ~/artiq-dev/llvm-or1k
        $ git checkout b3a48efb2c05ed6cedc5395ae726c6a6573ef3ba
        $ cat ~/artiq-dev/artiq/patches/llvm/* | patch -p1

        $ cd ~/artiq-dev/llvm-or1k/tools
        $ git clone https://github.com/openrisc/clang-or1k clang
        $ cd ~/artiq-dev/llvm-or1k/tools/clang
        $ git checkout 02d831c7e7dc1517abed9cc96abdfb937af954eb
        $ cat ~/artiq-dev/artiq/patches/clang/* | patch -p1

        $ cd ~/artiq-dev/llvm-or1k
        $ mkdir build
        $ cd ~/artiq-dev/llvm-or1k/build
        $ ../configure --prefix=/usr/local/llvm-or1k
        $ make ENABLE_OPTIMIZED=1 REQUIRES_RTTI=1
        $ sudo -E make install ENABLE_OPTIMIZED=1 REQUIRES_RTTI=1

        $ cd ~/artiq-dev
        $ git clone https://github.com/llvmpy/llvmpy
        $ cd ~/artiq-dev/llvmpy
        $ git checkout 7af2f7140391d4f708adf2721e84f23c1b89e97a
        $ cat /path_to/artiq/patches/llvmpy/* | patch -p1
        $ LLVM_CONFIG_PATH=/usr/local/llvm-or1k/bin/llvm-config sudo -E python setup.py install

.. note::
    Compilation of LLVM can take more than 30 min on some machines.

* Install ARTIQ: ::

        $ cd ~/artiq-dev
        $ git clone https://github.com/m-labs/artiq # if not already done
        $ python3 setup.py develop --user

* Build the documentation: ::

        $ cd ~/artiq-dev/artiq/doc/manual
        $ make html

Xubuntu 14.04 dependencies
--------------------------

This command installs all the required packages: ::

    $ sudo apt-get install build-essential autoconf  automake autotools-dev dh-make devscripts fakeroot file git lintian patch patchutils perl xutils-devs git-buildpackage svn-buildpackage python3-pip texinfo flex bison libmpc-dev python3-setuptools python3-numpy python3-scipy python3-sphinx python3-nose python3-dev subversion cmake libusb-dev libftdi-dev pkg-config

Note that ARTIQ requires Python 3.4 or above.
