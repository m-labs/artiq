Introduction
------------

.. this does not work because of relative paths for the logo:
   .. include:: ../../README.rst
   and including in README.rst does not work on github therefore just keep this content synchronized with README.rst

ARTIQ (Advanced Real-Time Infrastructure for Quantum physics) is a leading-edge control and data acquisition system for quantum information experiments.
It is maintained and developed by `M-Labs <https://m-labs.hk>`_ and the initial development was for and in partnership with the `Ion Storage Group at NIST <https://www.nist.gov/pml/time-and-frequency-division/ion-storage>`_. ARTIQ is free software and offered to the entire research community as a solution equally applicable to other challenging control tasks, including outside the field of ion trapping. Many laboratories around the world have adopted ARTIQ as their control system and some have `contributed <https://m-labs.hk/experiment-control/funding/>`_ to it.

The system features a high-level programming language, capable of describing complex experiments, which is compiled and executed on dedicated hardware with nanosecond timing resolution and sub-microsecond latency. It includes graphical user interfaces to parametrize and schedule experiments and to visualize and explore the results.

ARTIQ uses FPGA hardware to perform its time-critical tasks. The `Sinara hardware <https://github.com/sinara-hw>`_, and in particular the Kasli FPGA carrier, are designed to work with ARTIQ. ARTIQ is designed to be portable to hardware platforms from different vendors and FPGA manufacturers. Several different configurations of a `FPGA evaluation kit <https://www.xilinx.com/products/boards-and-kits/ek-k7-kc705-g.html>`_ and a `Zynq evaluation kit <https://www.xilinx.com/products/boards-and-kits/ek-z7-zc706-g.html>`_ are also used and supported. FPGA platforms can be combined with any number of additional peripherals, either already accessible from ARTIQ or made accessible with little effort.

ARTIQ and its dependencies are available in the form of Nix packages (for Linux) and MSYS2 packages (for Windows). See `the manual <https://m-labs.hk/experiment-control/resources/>`_ for installation instructions. Packages containing pre-compiled binary images to be loaded onto the hardware platforms are supplied for each configuration. Like any open-source software ARTIQ can equally be built and installed directly from `source <https://github.com/m-labs/artiq>`_.

ARTIQ is supported by M-Labs and developed openly. Components, features, fixes, improvements, and extensions are often `funded <https://m-labs.hk/experiment-control/funding/>`_ by and developed for the partnering research groups.

Core technologies employed include `Python <https://www.python.org/>`_, `Migen <https://github.com/m-labs/migen>`_, `Migen-AXI <https://github.com/peteut/migen-axi>`_, `Rust <https://www.rust-lang.org/>`_, `MiSoC <https://github.com/m-labs/misoc>`_/`VexRiscv <https://github.com/SpinalHDL/VexRiscv>`_, `LLVM <https://llvm.org/>`_/`llvmlite <https://github.com/numba/llvmlite>`_, and `Qt6 <https://www.qt.io/>`_.

| Website: https://m-labs.hk/experiment-control/artiq
| (US-hosted mirror: https://m-labs-intl.com/experiment-control/artiq)

`Cite ARTIQ <http://dx.doi.org/10.5281/zenodo.51303>`_ as ``Bourdeauducq, Sébastien et al. (2016). ARTIQ 1.0. Zenodo. 10.5281/zenodo.51303``.

Copyright (C) 2014-2025 M-Labs Limited. Licensed under GNU LGPL version 3+.
