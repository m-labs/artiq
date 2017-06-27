.. Always keep doc/manual/introduction.rst synchronized with this file, with the exception of the logo.

.. Absolute so that it works on github and on pypi
.. image:: https://raw.githubusercontent.com/m-labs/artiq/master/doc/logo/artiq.png
  :target: https://m-labs.hk/artiq

ARTIQ (Advanced Real-Time Infrastructure for Quantum physics) is the next-generation control system for quantum information experiments.
It is developed by `M-Labs <https://m-labs.hk>`_ for and in partnership with the `Ion Storage Group at NIST <http://www.nist.gov/pml/div688/grp10/index.cfm>`_ as free software.
It is offered to the entire research community as a solution equally applicable to other challenging control tasks outside the field of ion trapping.

The system features a high-level programming language that helps describing complex experiments, which is compiled and executed on dedicated hardware with nanosecond timing resolution and sub-microsecond latency. It includes graphical user interfaces to parametrize and schedule experiments and to visualize and explore the results.

ARTIQ uses FPGA hardware to perform its time-critical tasks.
It is designed to be portable to hardware platforms from different vendors and FPGA manufacturers.
Currently, several different configurations of a `high-end FPGA evaluation kit <http://www.xilinx.com/products/boards-and-kits/ek-k7-kc705-g.html>`_ are used and supported. This FPGA platform can be combined with any number of additional peripherals, either already accessible from ARTIQ or made accessible with little effort.

Custom hardware components with widely extended capabilities and advanced support for scalable and fully distributed real-time control of experiments `are being designed <https://github.com/m-labs/artiq-hardware>`_.

ARTIQ and its dependencies are available in the form of `conda packages <https://conda.anaconda.org/m-labs/label/main>`_ for both Linux and Windows.
Packages containing pre-compiled binary images to be loaded onto the hardware platforms are supplied for each configuration.
Like any open source software ARTIQ can equally be built and installed directly from `source <https://github.com/m-labs/artiq>`_.

ARTIQ is supported by M-Labs and developed openly.
Components, features, fixes, improvements, and extensions are funded by and developed for the partnering research groups.

Technologies employed include `Python <https://www.python.org/>`_, `Migen <https://github.com/m-labs/migen>`_, `MiSoC <https://github.com/m-labs/misoc>`_/`mor1kx <https://github.com/openrisc/mor1kx>`_, `LLVM <http://llvm.org/>`_/`llvmlite <https://github.com/numba/llvmlite>`_, and `Qt5 <http://www.qt.io/>`_.

Website: https://m-labs.hk/artiq

`Cite ARTIQ <http://dx.doi.org/10.5281/zenodo.51303>`_ as ``Bourdeauducq, Sébastien et al. (2016). ARTIQ 1.0. Zenodo. 10.5281/zenodo.51303``.

License
=======

Copyright (C) 2014-2017 M-Labs Limited.

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
