Developing ARTIQ
^^^^^^^^^^^^^^^^

.. note::
    Developing ARTIQ is currently only possible on Linux.

We describe two different approaches to creating a development environment for ARTIQ.

The first method uses existing pre-compiled Anaconda packages and the ``artiq-dev`` meta-package for the development environment.
This is fast and convenient because it avoids compiling the entire toolchain.
Consequently, some ARTIQ developers as well as the buildbot that's used for continuous integration all employ this method to build the ``artiq`` Anaconda packages and the bitstreams.
It is completely sufficient to develop and tweak the ARTIQ code and to build
bitstreams.

But with the meta-pakage developing individual components within the toolchain requires extra care.
Consequently, the second method builds most components in the toolchain from their sources.
This takes time and care to reproduce accurately but it gives absolute control over the components and an immediate handle at developing them.
Some ARTIQ developers use this second method of building the entire toolchain
from sources.
It is only recommended for developers and advanced users.

.. _develop-from-conda:

ARTIQ Anaconda development environment
======================================

    1. Install ``git`` as recommended for your operating system and distribution.
    2. Obtain ARTIQ::

           $ git clone --recursive https://github.com/m-labs/artiq ~/artiq-dev/artiq
           $ cd ~/artiq-dev/artiq

       Add ``-b release-X`` to the ``git clone`` command if you are building a stable branch of ARTIQ. Replace ``X`` with the major release. The default will fetch the development ``master`` branch.
    3. :ref:`Install Anaconda or Miniconda <install-anaconda>`
    4. Create and activate a conda environment named ``artiq-dev`` and install the ``artiq-dev`` package which pulls in all the packages required to develop ARTIQ::

           $ conda env create -f conda/artiq-dev.yaml
           $ source activate artiq-dev
    5. Add the ARTIQ source tree to the environment's search path::

           $ pip install -e .
    6. :ref:`Install Vivado <install-xilinx>`
    7. :ref:`Configure OpenOCD <setup-openocd>`
    8. :ref:`Build target binaries <build-target-binaries>`
    9. :ref:`Flash target binaries <flash-target-binaries>`

.. _install-from-source:

Installing ARTIQ from source
============================

Preparing the build environment for the core device
---------------------------------------------------

These steps are required to generate code that can run on the core
device. They are necessary both for building the MiSoC BIOS
and the ARTIQ kernels.

* Install required host packages: ::

        $ sudo apt-get install python3.5 pip3 build-essential cmake cargo

* Create a development directory: ::

        $ mkdir ~/artiq-dev

* Clone ARTIQ repository: ::

        $ cd ~/artiq-dev
        $ git clone --recursive https://github.com/m-labs/artiq

    Add ``-b release-X`` to the ``git clone`` command if you are building a stable branch of ARTIQ (the default will fetch the development ``master`` branch).

* Install OpenRISC binutils (or1k-linux-...): ::

        $ cd ~/artiq-dev
        $ wget https://ftp.gnu.org/gnu/binutils/binutils-2.27.tar.bz2
        $ tar xvf binutils-2.27.tar.bz2
        $ cd binutils-2.27
        $ curl -L 'https://raw.githubusercontent.com/m-labs/conda-recipes/c3effbc26e96c6e246d6e8035f8a07bc52d8ded1/conda/binutils-or1k-linux/fix-R_OR1K_GOTOFF-relocations.patch' | patch -p1

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
        $ git clone -b artiq-4.0 https://github.com/m-labs/llvm-or1k
        $ cd llvm-or1k
        $ git clone -b artiq-4.0 https://github.com/m-labs/clang-or1k tools/clang

        $ mkdir build
        $ cd build
        $ cmake .. -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr/local/llvm-or1k -DLLVM_TARGETS_TO_BUILD=X86 -DLLVM_EXPERIMENTAL_TARGETS_TO_BUILD=OR1K -DLLVM_ENABLE_ASSERTIONS=ON -DLLVM_INSTALL_UTILS=ON -DCLANG_ENABLE_ARCMT=OFF -DCLANG_ENABLE_STATIC_ANALYZER=OFF
        $ make -j4
        $ sudo make install

* Install Rust: ::

        $ cd ~/artiq-dev
        $ git clone -b artiq-1.23.0 https://github.com/m-labs/rust
        $ cd rust
        $ git submodule update --init --recursive
        $ mkdir build
        $ cd build
        $ ../configure --prefix=/usr/local/rust-or1k --llvm-root=/usr/local/llvm-or1k --disable-manage-submodules --disable-docs
        $ sudo mkdir /usr/local/rust-or1k
        $ sudo chown $USER.$USER /usr/local/rust-or1k
        $ make install

        $ libs="core std_unicode alloc"
        $ rustc="/usr/local/rust-or1k/bin/rustc --target or1k-unknown-none -C target-feature=+mul,+div,+ffl1,+cmov,+addc -C opt-level=s -g --crate-type rlib -L ."
        $ destdir="/usr/local/rust-or1k/lib/rustlib/or1k-unknown-none/lib/"
        $ mkdir ../build-or1k
        $ cd ../build-or1k
        $ for lib in ${libs}; do ${rustc} --crate-name ${lib} ../src/lib${lib}/lib.rs; done
        $ ${rustc} --crate-name libc ../src/liblibc_mini/lib.rs
        $ ${rustc} --crate-name unwind ../src/libunwind/lib.rs
        $ ${rustc} -Cpanic=abort --crate-name panic_abort ../src/libpanic_abort/lib.rs
        $ ${rustc} -Cpanic=unwind --crate-name panic_unwind ../src/libpanic_unwind/lib.rs --cfg llvm_libunwind
        $ mkdir -p ${destdir}
        $ cp *.rlib ${destdir}

.. note::
    Compilation of LLVM can take more than 30 min on some machines. Compilation of Rust can take more than two hours.

Preparing the core device FPGA board
------------------------------------

These steps are required to generate gateware bitstream (``.bit``) files, build the MiSoC BIOS and ARTIQ runtime, and flash FPGA boards. If the board is already flashed, you may skip those steps and go directly to `Installing the host-side software`.

.. _install-xilinx:

* Install the FPGA vendor tools (i.e. Vivado):

    * Get Vivado from http://www.xilinx.com/support/download/index.htm.

    * The "appropriate" Vivado version to use for building the bitstream can
      vary. Some versions contain bugs that lead to hidden or visible failures,
      others work fine.
      Refer to the `M-Labs buildbot logs <http://buildbot.m-labs.hk/>`_ to
      determine which version is currently used when building the binary
      packages.

    * During the Vivado installation, uncheck ``Install cable drivers`` (they are not required as we use better and open source alternatives).

* Install Migen: ::

        $ cd ~/artiq-dev
        $ git clone https://github.com/m-labs/migen
        $ cd migen
        $ python3 setup.py develop --user

.. note::
    The options ``develop`` and ``--user`` are for setup.py to install Migen in ``~/.local/lib/python3.5``.

.. _install-bscan-spi:

* Install the required flash proxy gateware bitstreams:

    The purpose of the flash proxy gateware bitstream is to give programming software fast JTAG access to the flash connected to the FPGA.

    * KC705:

        ::

            $ cd ~/artiq-dev
            $ wget https://raw.githubusercontent.com/jordens/bscan_spi_bitstreams/master/bscan_spi_xc7k325t.bit

        Then move ``~/artiq-dev/bscan_spi_xc7k325t.bit`` to ``~/.migen``, ``/usr/local/share/migen``, or ``/usr/share/migen``.

* :ref:`Download and install OpenOCD <install-openocd>`.

* Download and install ``asyncserial``: ::

        $ cd ~/artiq-dev
        $ git clone https://www.github.com/m-labs/asyncserial
        $ cd asyncserial
        $ python3 setup.py develop --user

* Download and install MiSoC: ::

        $ cd ~/artiq-dev
        $ git clone --recursive https://github.com/m-labs/misoc
        $ cd misoc
        $ python3 setup.py develop --user

* Download and install ``pythonparser``: ::

        $ cd ~/artiq-dev
        $ git clone https://www.github.com/m-labs/pythonparser
        $ cd pythonparser
        $ python3 setup.py develop --user

* Download and install ARTIQ: ::

        $ cd ~/artiq-dev
        $ git clone --recursive https://github.com/m-labs/artiq
        $ cd artiq
        $ python3 setup.py develop --user

.. note::
    If you have any trouble during ARTIQ setup about ``pygit2`` installation,
    refer to the section dealing with
    :ref:`installing the host-side software <installing-the-host-side-software>`.


* Build the gateware bitstream, BIOS and runtime by running:
    ::

        $ cd ~/artiq-dev
        $ export PATH=/usr/local/llvm-or1k/bin:$PATH

    .. note:: Make sure that ``/usr/local/llvm-or1k/bin`` is first in your ``PATH``, so that the ``clang`` command you just built is found instead of the system one, if any.

.. _build-target-binaries:

    * For KC705::

        $ python3 -m artiq.gateware.targets.kc705 -V nist_clock # or nist_qc2

    .. note:: Add ``--toolchain ise`` if you wish to use ISE instead of Vivado. ISE needs a separate installation step.

.. _flash-target-binaries:

* Then, gather the binaries and flash them: ::

        $ mkdir binaries
        $ cp misoc_nist_qcX_<board>/gateware/top.bit binaries
        $ cp misoc_nist_qcX_<board>/software/bios/bios.bin binaries
        $ cp misoc_nist_qcX_<board>/software/runtime/runtime.fbi binaries
        $ artiq_flash -d binaries

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
        $ git checkout artiq-3.9
        $ LLVM_CONFIG=/usr/local/llvm-or1k/bin/llvm-config python3 setup.py install --user

* Install ARTIQ: ::

        $ cd ~/artiq-dev
        $ git clone --recursive https://github.com/m-labs/artiq # if not already done
        $ cd artiq
        $ python3 setup.py develop --user

.. note::
    If you have any trouble during ARTIQ setup about ``pygit2`` installation,
    you can install it by using ``pip``:

    On Ubuntu 14.04::

        $ python3 `which pip3` install --user pygit2==0.19.1

    On Ubuntu 14.10::

        $ python3 `which pip3` install --user pygit2==0.20.3

    On Ubuntu 15.04 and 15.10::

        $ python3 `which pip3` install --user pygit2==0.22.1

    On Ubuntu 16.04::

        $ python3 `which pip3` install --user pygit2==0.24.1

    The rationale behind this is that pygit2 and libgit2 must have the same
    major.minor version numbers.

    See http://www.pygit2.org/install.html#version-numbers

* Build the documentation: ::

        $ cd ~/artiq-dev/artiq/doc/manual
        $ make html
