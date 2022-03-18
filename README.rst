.. Always keep doc/manual/introduction.rst synchronized with this file, with the exception of the logo.

.. Absolute so that it works on github and on pypi
.. image:: https://raw.githubusercontent.com/m-labs/artiq/master/doc/logo/artiq.png
  :target: https://m-labs.hk/artiq

ARTIQ (Advanced Real-Time Infrastructure for Quantum physics) is a leading-edge control and data acquisition system for quantum information experiments.
It is maintained and developed by `M-Labs <https://m-labs.hk>`_ and the initial development was for and in partnership with the `Ion Storage Group at NIST <https://www.nist.gov/pml/time-and-frequency-division/ion-storage>`_. ARTIQ is free software and offered to the entire research community as a solution equally applicable to other challenging control tasks, including outside the field of ion trapping. Many laboratories around the world have adopted ARTIQ as their control system, with over a hundred Sinara hardware crates deployed, and some have `contributed <https://m-labs.hk/experiment-control/funding/>`_ to it.

The system features a high-level programming language that helps describing complex experiments, which is compiled and executed on dedicated hardware with nanosecond timing resolution and sub-microsecond latency. It includes graphical user interfaces to parametrize and schedule experiments and to visualize and explore the results.

ARTIQ uses FPGA hardware to perform its time-critical tasks. The `Sinara hardware <https://github.com/sinara-hw>`_, and in particular the Kasli FPGA carrier, is designed to work with ARTIQ.
ARTIQ is designed to be portable to hardware platforms from different vendors and FPGA manufacturers.
Several different configurations of a `FPGA evaluation kit <https://www.xilinx.com/products/boards-and-kits/ek-k7-kc705-g.html>`_ and of a `Zynq evaluation kit <https://www.xilinx.com/products/boards-and-kits/ek-z7-zc706-g.html>`_ are also used and supported. FPGA platforms can be combined with any number of additional peripherals, either already accessible from ARTIQ or made accessible with little effort.

ARTIQ and its dependencies are available in the form of Nix packages (for Linux) and Conda packages (for Windows and Linux). See `the manual <https://m-labs.hk/experiment-control/resources/>`_ for installation instructions.
Packages containing pre-compiled binary images to be loaded onto the hardware platforms are supplied for each configuration.
Like any open source software ARTIQ can equally be built and installed directly from `source <https://github.com/m-labs/artiq>`_.

ARTIQ is supported by M-Labs and developed openly.
Components, features, fixes, improvements, and extensions are often `funded <https://m-labs.hk/experiment-control/funding/>`_ by and developed for the partnering research groups.

Core technologies employed include `Python <https://www.python.org/>`_, `Migen <https://github.com/m-labs/migen>`_, `Migen-AXI <https://github.com/peteut/migen-axi>`_, `Rust <https://www.rust-lang.org/>`_, `MiSoC <https://github.com/m-labs/misoc>`_/`VexRiscv <https://github.com/SpinalHDL/VexRiscv>`_, `LLVM <https://llvm.org/>`_/`llvmlite <https://github.com/numba/llvmlite>`_, and `Qt5 <https://www.qt.io/>`_.

Website: https://m-labs.hk/artiq

`Cite ARTIQ <http://dx.doi.org/10.5281/zenodo.51303>`_ as ``Bourdeauducq, Sébastien et al. (2016). ARTIQ 1.0. Zenodo. 10.5281/zenodo.51303``.

License
=======

Copyright (C) 2014-2022 M-Labs Limited.

ARTIQ is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

ARTIQ is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License
along with ARTIQ.  If not, see <http://www.gnu.org/licenses/>.

The ARTIQ manifesto
===================

The free and open dissemination of methods and results is central to scientific progress.

The ARTIQ and Sinara authors, contributors, and supporters consider the free and open exchange of scientific tools to be equally important and have chosen the licensing terms of ARTIQ and Sinara accordingly. ARTIQ, including its gateware, the firmware, and the ARTIQ tools and libraries are licensed as LGPLv3+. The Sinara hardware designs are licensed under CERN OHL.
This ensures that a user of ARTIQ or Sinara hardware designs obtains broad rights to use, redistribute, study, and modify them.

The following statements are intended to clarify the interpretation and application of the licensing terms:

* There is no requirement to distribute any unmodified, modified, or extended versions of ARTIQ. Only when distributing ARTIQ the source needs to be made available.
* Unmodified, modified, or extended versions of ARTIQ can be distributed freely under the terms of the LGPLv3+.
* Your ``Experiments``, ``Applets``, and ARTIQ device drivers are considered "Applications" (see the LGPLv3+) and can be (but don't have to be) distributed under the terms of your choice. The public distribution under a free and open license is encouraged, however.
* Similarly, distribution and licensing of your experiment data, calibrations, or measurement results is entirely at your discretion.
* Other features, changes, and additions are considered modifications of ARTIQ and inherit the LGPLv3+. Those include for example adding new RTIO ``Phys``, compiler optimizations, compiler features, ports of the compiler to other target CPUs, dashboard or browser features that are not in applets, as well as scheduler, master and runtime modifications.
* Analogously to the established practice in the Linux kernel, we do not consider components that are developed and used independently to be modifications of ARTIQ.
* For example, when developing a ``Phy`` for an independently developed and used gateware component, that gateware component is not considered a modification of ARTIQ (but the ``Phy`` is).
