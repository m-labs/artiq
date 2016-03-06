Install ARTIQ via the Nix Package Manager
===========================

Nix does not support windows.

* Install the nix package manager

  * many linux distros already have a package for the `nix package manager <http://nixos.org/nix/>`_

    * for example: $ apt-get install nix

  * if you would like to install via sh (please be sure you `understand <https://www.seancassidy.me/dont-pipe-to-your-shell.html>`_ the dangers involved when curl piping to sh. Also ensure you have read the contents of the script and feel comfortable executing it. Otherwise there is the `manual <http://nixos.org/nix/manual/>`_)

    * $ curl https://nixos.org/nix/install | sh

    * $ source ~/.nix-profile/etc/profile.d/nix.sh

* $ git clone github.com/m-labs/artiq
* $ cd artiq/nix
* $ nix-env -i -f default.nix

The above command will setup your entire environment.
