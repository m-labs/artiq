.. _install-from-source:

Installing ARTIQ from source
============================

.. note::
	This method is only recommended for developers and advanced users. An easier way to install ARTIQ is via the Anaconda packages (see :ref:`Installing ARTIQ <install-from-conda>`).


Preparing the build environment for the core device
---------------------------------------------------

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
------------------------------------

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

        $ python3.5 -m artiq.gateware.targets.kc705 -H nist_qc1  # or nist_qc2

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
---------------------------------

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
