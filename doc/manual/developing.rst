.. _developing-artiq:

Developing ARTIQ
^^^^^^^^^^^^^^^^

.. warning::
    This section is only for software or FPGA developers who want to modify ARTIQ. The steps described here are not required if you simply want to run experiments with ARTIQ. If you purchased a system from M-Labs or QUARTIQ, we normally provide board binaries for you.

The easiest way to obtain an ARTIQ development environment is via the Nix package manager on Linux. The Nix system is used on the `M-Labs Hydra server <https://nixbld.m-labs.hk/>`_ to build ARTIQ and its dependencies continuously; it ensures that all build instructions are up-to-date and allows binary packages to be used on developers' machines, in particular for large tools such as the Rust compiler.
ARTIQ itself does not depend on Nix, and it is also possible to compile everything from source (look into the ``flake.nix`` file and/or nixpkgs, and run the commands manually) - but Nix makes the process a lot easier.

* Download Vivado from Xilinx and install it (by running the official installer in a FHS chroot environment if using NixOS; the ARTIQ flake provides such an environment). If you do not want to write to ``/opt``, you can install it in a folder of your home directory. The "appropriate" Vivado version to use for building the bitstream can vary. Some versions contain bugs that lead to hidden or visible failures, others work fine. Refer to `Hydra <https://nixbld.m-labs.hk/>`_ and/or the ``flake.nix`` file from the ARTIQ repository in order to determine which version is used at M-Labs. If the Vivado GUI installer crashes, you may be able to work around the problem by running it in unattended mode with a command such as ``./xsetup -a XilinxEULA,3rdPartyEULA,WebTalkTerms -b Install -e 'Vitis Unified Software Platform' -l /opt/Xilinx/``.
* During the Vivado installation, uncheck ``Install cable drivers`` (they are not required as we use better and open source alternatives).
* Install the `Nix package manager <http://nixos.org/nix/>`_, version 2.4 or later. Prefer a single-user installation for simplicity.
* If you did not install Vivado in its default location ``/opt``, clone the ARTIQ Git repository and edit ``flake.nix`` accordingly.
* Enable flakes in Nix by e.g. adding ``experimental-features = nix-command flakes`` to ``nix.conf`` (for example ``~/.config/nix/nix.conf``).
* Enter the development shell by running ``nix develop git+https://github.com/m-labs/artiq.git``, or alternatively by cloning the ARTIQ Git repository and running ``nix develop`` at the root (where ``flake.nix`` is).
* You can then build the firmware and gateware with a command such as ``$ python -m artiq.gateware.targets.kasli``. If you are using a JSON system description file, use ``$ python -m artiq.gateware.targets.kasli_generic file.json``.
* Flash the binaries into the FPGA board with a command such as ``$ artiq_flash --srcbuild -d artiq_kasli/<your_variant>``. You need to configure OpenOCD as explained :ref:`in the user section <configuring-openocd>`. OpenOCD is already part of the flake's development environment.
* Check that the board boots and examine the UART messages by running a serial terminal program, e.g. ``$ flterm /dev/ttyUSB1`` (``flterm`` is part of MiSoC and installed in the flake's development environment). Leave the terminal running while you are flashing the board, so that you see the startup messages when the board boots immediately after flashing. You can also restart the board (without reflashing it) with ``$ artiq_flash start``.
* The communication parameters are 115200 8-N-1. Ensure that your user has access to the serial device (e.g. by adding the user account to the ``dialout`` group).


.. warning::
    Nix will make a read-only copy of the ARTIQ source to use in the shell environment. Therefore, any modifications that you make to the source after the shell is started will not be taken into account. A solution applicable to ARTIQ (and several other Python packages such as Migen and MiSoC) is to prepend the ARTIQ source directory to the ``PYTHONPATH`` environment variable after entering the shell. If you want this to be done by default, edit the ``devShell`` section of ``flake.nix``.
