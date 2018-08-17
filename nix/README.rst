Install ARTIQ via the Nix Package Manager
=========================================

These instructions provide an alternative route to install ARTIQ for people who do not wish to use conda.

This sets up an environment suitable for using ARTIQ, including the ARTIQ-Python compiler, device drivers, and the graphical user interfaces. This works correctly on Linux, and partially works (but not to a level that we would consider usable) with WSL introduced in Windows 10.

ARTIQ firmware and gateware development tools (e.g. rustc, Migen) and ARTIQ core device flashing tools (OpenOCD, proxy bitstreams) are currently not available on Nix. Pull requests welcome!

* Install the Nix package manager

  * many Linux distros already have a package for the `Nix package manager <http://nixos.org/nix/>`_

    * for example: ``$ apt-get install nix``

  * if you would like to install via sh

    * $ ``wget https://nixos.org/nix/install``

    * $ ``sh install``

    * $ ``source ~/.nix-profile/etc/profile.d/nix.sh``

* $ ``git clone github.com/m-labs/artiq``
* $ ``cd artiq/nix``
* $ ``nix-env -i -f default.nix``

The above command will setup your entire environment. Note that it will compile LLVM and Clang, which uses a lot of CPU time and disk space.
