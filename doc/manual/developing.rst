Developing ARTIQ
^^^^^^^^^^^^^^^^

.. warning::
    This section is only for software or FPGA developers who want to modify ARTIQ. The steps described here are not required if you simply want to run experiments with ARTIQ. If you purchased a system from M-Labs or QUARTIQ, we normally provide board binaries for you.

The easiest way to obtain an ARTIQ development environment is via the Nix package manager on Linux. The Nix system is used on the `M-Labs Hydra server <https://nixbld.m-labs.hk/>`_ to build ARTIQ and its dependencies continuously; it ensures that all build instructions are up-to-date and allows binary packages to be used on developers' machines, in particular for large tools such as the Rust compiler.
ARTIQ itself does not depend on Nix, and it is also possible to compile everything from source (look into the ``.nix`` files from the ``nix-scripts`` repository and run the commands manually) - but Nix makes the process a lot easier.

* Install the `Nix package manager <http://nixos.org/nix/>`_ and Git (e.g. ``$ nix-shell -p git``).
* Set up the M-Labs Hydra channels (:ref:`same procedure as the user section <installing-nix-users>`) to allow binaries to be downloaded. Otherwise, tools such as LLVM and the Rust compiler will be compiled on your machine, which uses a lot of CPU time, memory, and disk space. Simply setting up the channels is sufficient, Nix will automatically detect when a binary can be downloaded instead of being compiled locally.
* Clone the repositories https://github.com/m-labs/artiq and https://git.m-labs.hk/m-labs/nix-scripts.
* Run ``$ nix-shell -I artiqSrc=path_to_artiq_sources shell-dev.nix`` to obtain an environment containing all the required development tools (e.g. Migen, MiSoC, Clang, Rust, OpenOCD...)  in addition to the ARTIQ user environment. ``artiqSrc`` should point to the root of the cloned ``artiq`` repository, and ``shell-dev.nix`` can be found in the ``artiq-fast`` folder of the ``nix-scripts`` repository.
* This enters a FHS chroot environment that simplifies the installation and patching of Xilinx Vivado.
* Download Vivado from Xilinx and install it (by running the official installer in the FHS chroot environment). If you do not want to write to ``/opt``, you can install it in a folder of your home directory. The "appropriate" Vivado version to use for building the bitstream can vary. Some versions contain bugs that lead to hidden or visible failures, others work fine. Refer to the `M-Labs Hydra logs <https://nixbld.m-labs.hk/>`_ to determine which version is currently used when building the binary packages.
* During the Vivado installation, uncheck ``Install cable drivers`` (they are not required as we use better and open source alternatives).
* You can then build the firmware and gateware with a command such as ``$ python -m artiq.gateware.targets.kasli``.
* If you did not install Vivado in ``/opt``, add a command line option such as ``--gateware-toolchain-path ~/Xilinx/Vivado``.
* Flash the binaries into the FPGA board with a command such as ``$ artiq_flash --srcbuild artiq_kasli -V <your_variant>``. You need to configure OpenOCD as explained :ref:`in the user section <configuring-openocd>`. OpenOCD is already part of the shell started by ``shell-dev.nix``.
* Check that the board boots and examine the UART messages by running a serial terminal program, e.g. ``$ flterm /dev/ttyUSB1`` (``flterm`` is part of MiSoC and installed by ``shell-dev.nix``). Leave the terminal running while you are flashing the board, so that you see the startup messages when the board boots immediately after flashing. You can also restart the board (without reflashing it) with ``$ artiq_flash start``.
* The communication parameters are 115200 8-N-1. Ensure that your user has access to the serial device (``$ sudo adduser $USER dialout`` assuming standard setup).
* If you are modifying a dependency of ARTIQ, in addition to updating the relevant part of ``nix-scripts``, rebuild and upload the corresponding Conda packages manually, and update their version numbers in ``conda-artiq.nix``. For Conda, only the main ARTIQ package and the board packages are handled automatically on Hydra.

.. warning::
    Nix will make a read-only copy of the ARTIQ source to use in the shell environment. Therefore, any modifications that you make to the source after the shell is started will not be taken into account. A solution applicable to ARTIQ (and several other Python packages such as Migen and MiSoC) is to prepend the ARTIQ source directory to the ``PYTHONPATH`` environment variable after entering the shell. If you want this to be done by default, edit ``profile`` in ``artiq-dev.nix``.
