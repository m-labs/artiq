Use ARTIQ via the Nix Package Manager
=====================================

These instructions provide an alternative route to install ARTIQ for people who do not wish to use conda.

This sets up an environment suitable for using ARTIQ, including the ARTIQ-Python compiler, device drivers, and the graphical user interfaces. This works correctly on Linux, and partially works (but not to a level that we would consider usable) with WSL introduced in Windows 10.

* Install the Nix package manager

  * many Linux distros already have a package for the `Nix package manager <http://nixos.org/nix/>`_

    * for example: ``$ apt-get install nix``

  * if you would like to install via sh

    * $ ``wget https://nixos.org/nix/install``

    * $ ``sh install``

    * $ ``source ~/.nix-profile/etc/profile.d/nix.sh``

* $ ``nix-channel --add https://nixbld.m-labs.hk/project/artiq/channel/latest m-labs``
* $ ``nix-channel --update``
* create the file ``~/.config/nix/nix.conf`` with the following content:
``
substituters = https://cache.nixos.org https://nixbld.m-labs.hk
trusted-public-keys = cache.nixos.org-1:6NCHdD59X431o0gWypbMrAURkbJ16ZPMQFGspcDShjY= nixbld.m-labs.hk-1:5aSRVA5b320xbNvu30tqxVPXpld73bhtOeH6uAjRyHc=
``
* $ ``nix-env -i python3.6-artiq``

ARTIQ development environment with Nix
======================================

Run ``nix-shell shell-dev.nix`` to obtain an environment containing Migen, MiSoC, Microscope, jesd204b, Clang, Rust, Cargo, and OpenOCD in addition to the user environment above.

This creates a FHS chroot environment in order to simplify the installation and patching of Xilinx Vivado (it needs to be installed manually e.g. in your home folder).

You can then build the firmware and gateware with a command such as ``python -m artiq.gateware.targets.kasli --gateware-toolchain-path ~/Xilinx/Vivado``.
