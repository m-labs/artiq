Installing ARTIQ
================

ARTIQ can be installed using the Nix (on Linux) or MSYS2 (on Windows) package managers. Using Conda is also possible on both platforms but not recommended.

Installing via Nix (Linux)
--------------------------

First install the Nix package manager. Some distributions provide a package for it; otherwise, it can be installed via the script on the `Nix website <http://nixos.org/nix/>`_. Make sure you get Nix version 2.4 or higher. Prefer a single-user installation for simplicity.

Once Nix is installed, enable flakes, for example by running: ::

  $ mkdir -p ~/.config/nix
  $ echo "experimental-features = nix-command flakes" >> ~/.config/nix/nix.conf

See also the different options for enabling flakes on `the NixOS wiki <https://nixos.wiki/wiki/flakes>`_.

The easiest way to obtain ARTIQ is to install it into the user environment with ::

  $ nix profile install git+https://github.com/m-labs/artiq.git

Answer "Yes" to the questions about setting Nix configuration options (for more details see 'Troubleshooting' below.) You should now have a minimal installation of ARTIQ, where the usual front-end commands (:mod:`~artiq.frontend.artiq_run`, :mod:`~artiq.frontend.artiq_master`, :mod:`~artiq.frontend.artiq_dashboard`, etc.) are all available to you.

This installation is however quite limited, as Nix creates a dedicated Python environment for the ARTIQ commands alone. This means that other useful Python packages, which ARTIQ is not dependent on but which you may want to use in your experiments (pandas, matplotlib...), are not available.

Installing multiple packages and making them visible to the ARTIQ commands requires using the Nix language. Create an empty directory with a file ``flake.nix`` with the following contents:

::

  {
    inputs.extrapkg.url = "git+https://git.m-labs.hk/M-Labs/artiq-extrapkg.git";
    outputs = { self, extrapkg }:
      let
        pkgs = extrapkg.pkgs;
        artiq = extrapkg.packages.x86_64-linux;
      in {
        defaultPackage.x86_64-linux = pkgs.buildEnv {
          name = "artiq-env";
          paths = [
            # ========================================
            # EDIT BELOW
            # ========================================
            (pkgs.python3.withPackages(ps: [
              # List desired Python packages here.
              artiq.artiq
              #ps.paramiko  # needed if and only if flashing boards remotely (artiq_flash -H)
              #artiq.flake8-artiq
              #artiq.dax
              #artiq.dax-applets

              # The NixOS package collection contains many other packages that you may find
              # interesting. Here are some examples:
              #ps.pandas
              #ps.numba
              #ps.matplotlib
              # or if you need Qt (will recompile):
              #(ps.matplotlib.override { enableQt = true; })
              #ps.bokeh
              #ps.cirq
              #ps.qiskit
              # Note that NixOS also provides packages ps.numpy and ps.scipy, but it is
              # not necessary to explicitly add these, since they are dependencies of
              # ARTIQ and available with an ARTIQ install anyway.
            ]))
            #artiq.korad_ka3005p
            #artiq.novatech409b
            # List desired non-Python packages here
            # Other potentially interesting non-Python packages from the NixOS package collection:
            #pkgs.gtkwave
            #pkgs.spyder
            #pkgs.R
            #pkgs.julia
            # ========================================
            # EDIT ABOVE
            # ========================================
          ];
        };
      };
    nixConfig = {  # work around https://github.com/NixOS/nix/issues/6771
      extra-trusted-public-keys = "nixbld.m-labs.hk-1:5aSRVA5b320xbNvu30tqxVPXpld73bhtOeH6uAjRyHc=";
      extra-substituters = "https://nixbld.m-labs.hk";
    };
  }

You can now spawn a shell containing these packages by running ``$ nix shell`` in the directory containing the ``flake.nix``. This should make both the ARTIQ commands and all the additional packages available to you. You can exit the shell with Control+D or with the command  ``exit``. A first execution of ``$ nix shell`` may take some time, but for any future repetitions Nix will use cached packages and startup should be much faster.

You might be interested in creating multiple directories containing different ``flake.nix`` files which represent different sets of packages for different purposes. If you are familiar with Conda, using Nix in this way is similar to having multiple Conda environments.

To find more packages you can browse the `Nix package search <https://search.nixos.org/packages>`_ website. If your favorite package is not available with Nix, contact M-Labs using the helpdesk@ email.

.. note::
  If you find you prefer using flakes to your original ``nix profile`` installation, you can remove it from your system by running: ::

    $ nix profile list

  finding the entry with its ``Original flake URL`` listed as the GitHub ARTIQ repository, noting its index number (in a fresh Nix system it will normally be the only entry, at index 0), and running: ::

    $ nix profile remove [index]

  While using flakes, ARTIQ is not 'installed' as such in any permanent way. However, Nix will preserve independent cached packages in ``/nix/store`` for each flake, which over time or with many different flakes and versions can take up large amounts of storage space. To clear this cache, run ``$ nix-collect-garbage``.

.. _installing-troubleshooting:

Troubleshooting
^^^^^^^^^^^^^^^

"Do you want to allow configuration setting... (y/N)?"
""""""""""""""""""""""""""""""""""""""""""""""""""""""

When installing and initializing ARTIQ using commands like ``nix shell``, ``nix develop``, or ``nix profile install``, you may encounter prompts to modify certain configuration settings. These settings correspond to the ``nixConfig`` flag within the ARTIQ flake: ::

  do you want to allow configuration setting 'extra-sandbox-paths' to be set to '/opt' (y/N)?
  do you want to allow configuration setting 'extra-substituters' to be set to 'https://nixbld.m-labs.hk' (y/N)?
  do you want to allow configuration setting 'extra-trusted-public-keys' to be set to 'nixbld.m-labs.hk-1:5aSRVA5b320xbNvu30tqxVPXpld73bhtOeH6uAjRyHc=' (y/N)?

We recommend accepting these settings by responding with ``y``. If asked to permanently mark these values as trusted, choose ``y`` again. This action saves the configuration to ``~/.local/share/nix/trusted-settings.json``, allowing future prompts to be bypassed.

Alternatively, you can also use the option `accept-flake-config <https://nix.dev/manual/nix/stable/command-ref/conf-file#conf-accept-flake-config>`_ by appending ``--accept-flake-config`` to your nix command, for example: ::

  nix develop --accept-flake-config

Or add the option to ``~/.config/nix/nix.conf`` to make the setting more permanent: ::

  extra-experimental-features = flakes
  accept-flake-config = true

.. note::
  Should you wish to revert to the default settings, you can do so by editing the appropriate options in the aforementioned configuration files.

"Ignoring untrusted substituter, you are not a trusted user"
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

If the following message displays when running ``nix shell`` or ``nix develop`` ::

  warning: ignoring untrusted substituter 'https://nixbld.m-labs.hk', you are not a trusted user.
  Run `man nix.conf` for more information on the `substituters` configuration option.

and Nix proceeds to build some packages from source, this means that you are using `multi-user mode <https://nix.dev/manual/nix/stable/installation/multi-user>`_ in Nix, which may be the case for example when Nix is installed via ``pacman`` in Arch Linux. By default, users accessing Nix in multi-user mode are "unprivileged" and cannot use untrusted substituters. To change this, edit ``/etc/nix/nix.conf`` and add the following line (or append to the key if the key already exists): ::

  trusted-substituters = https://nixbld.m-labs.hk

This will add the substituter as a trusted substituter for all users using Nix.

Alternatively, add the following line: ::

  trusted-users = <username>  # Replace <username> with the user invoking `nix`

This will set your user as a trusted user, allowing the use of any untrusted substituters.

.. warning::

  Setting users as trusted users will effectively grant root access to those users. See the `Nix documentation <https://nixos.org/manual/nix/stable/command-ref/conf-file#conf-trusted-users>`_ for more information.

Installing via MSYS2 (Windows)
------------------------------

We recommend using our `offline installer <https://nixbld.m-labs.hk/job/artiq/extra-beta/msys2-offline-installer/latest>`_, which contains all the necessary packages and requires no additional configuration. After installation, simply launch ``MSYS2 with ARTIQ`` from the Windows Start menu.

Alternatively, you may install `MSYS2 <https://msys2.org>`_, then edit ``C:\MINGW64\etc\pacman.conf`` and add at the end: ::

    [artiq]
    SigLevel = Optional TrustAll
    Server = https://msys2.m-labs.hk/artiq-beta

Launch ``MSYS2 CLANG64`` from the Windows Start menu to open the MSYS2 shell, and enter the following commands: ::

  $  pacman -Syy
  $  pacman -S mingw-w64-clang-x86_64-artiq

As above in the Nix section, you may find yourself wanting to add other useful packages (pandas, matplotlib, etc.). MSYS2 uses a port of ArchLinux's ``pacman`` to manage (add, remove, and update) packages. To add a specific package, you can simply use a command of the form: ::

  $ pacman -S <package name>

For more see the `MSYS2 documentation <https://www.msys2.org/docs/package-management/>`_ on package management. If your favorite package is not available with MSYS2, contact M-Labs using the helpdesk@ email.

Installing via Conda [DEPRECATED]
---------------------------------

.. warning::
  Installing ARTIQ via Conda is not recommended. Instead, Linux users should install it via Nix and Windows users should install it via MSYS2. Conda support may be removed in future ARTIQ releases and M-Labs can only provide very limited technical support for Conda.

First, install `Anaconda <https://www.anaconda.com/download>`_ or the more minimalistic `Miniconda <https://conda.io/en/latest/miniconda.html>`_. After installing either Anaconda or Miniconda, open a new terminal and verify that the following command works::

    $ conda

Executing just ``conda`` should print the help of the ``conda`` command. If your shell cannot find the ``conda`` command, make sure that the Conda binaries are in your ``$PATH``. If ``$ echo $PATH`` does not show the Conda directories, add them: execute e.g. ``$ export PATH=$HOME/miniconda3/bin:$PATH`` if you installed Conda into ``~/miniconda3``.

Controllers for third-party devices (e.g. Thorlabs TCube, Lab Brick Digital Attenuator, etc.) that are not shipped with ARTIQ can also be installed with this script. Browse `Hydra <https://nixbld.m-labs.hk/project/artiq>`_ or see the list of NDSPs in this manual to find the names of the corresponding packages, and list them at the beginning of the script.

Set up the Conda channel and install ARTIQ into a new Conda environment: ::

    $ conda config --prepend channels https://conda.m-labs.hk/artiq-beta
    $ conda config --append channels conda-forge
    $ conda create -n artiq artiq

.. note::
  On Windows, if the last command that creates and installs the ARTIQ environment fails with an error similar to "seeking backwards is not allowed", try re-running the command with admin rights.

.. note::
  For commercial use you might need a license for Anaconda/Miniconda or for using the Anaconda package channel. `Miniforge <https://github.com/conda-forge/miniforge>`_ might be an alternative in a commercial environment as it does not include the Anaconda package channel by default. If you want to use Anaconda/Miniconda/Miniforge in a commercial environment, please check the license and the latest terms of service.

After the installation, activate the newly created environment by name. ::

    $ conda activate artiq

This activation has to be performed in every new shell you open to make the ARTIQ tools from that environment available.

.. _installing-upgrading:

Upgrading ARTIQ
---------------

.. note::
    When you upgrade ARTIQ, as well as updating the software on your host machine, it may also be necessary to reflash the gateware and firmware of your core device to keep them compatible. New numbered release versions in particular incorporate breaking changes and are not generally compatible. See :doc:`flashing` for instructions.

Upgrading with Nix
^^^^^^^^^^^^^^^^^^

Run ``$ nix profile upgrade`` if you installed ARTIQ into your user profile. If you used a ``flake.nix`` shell environment, make a back-up copy of the ``flake.lock`` file to enable rollback, then run ``$ nix flake update`` and re-enter the environment with ``$ nix shell``.

To rollback to the previous version, respectively use ``$ nix profile rollback`` or restore the backed-up version of the ``flake.lock`` file.

Upgrading with MSYS2
^^^^^^^^^^^^^^^^^^^^

Run ``pacman -Syu`` to update all MSYS2 packages, including ARTIQ. If you get a message telling you that the shell session must be restarted after a partial update, open the shell again after the partial update and repeat the command. See the `MSYS2 <https://www.msys2.org/docs/updating/>`__ and `Pacman <https://wiki.archlinux.org/title/Pacman>`_ manuals for more information, including how to update individual packages if required.

Upgrading with Conda
^^^^^^^^^^^^^^^^^^^^

When upgrading ARTIQ or when testing different versions it is recommended that new Conda environments are created instead of upgrading the packages in existing environments. As a rule, keep previous environments around unless you are certain that they are no longer needed and the new environment is working correctly.

To install the latest version, simply select a different environment name and run the installation commands again.

Switching between Conda environments using commands such as ``$ conda deactivate artiq-7`` and ``$ conda activate artiq-8`` is the recommended way to roll back to previous versions of ARTIQ.

You can list the environments you have created using::

    $ conda env list
