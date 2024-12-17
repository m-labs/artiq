NixOS for ARTIQ (preinstall handbook)
=====================================

This handbook assumes you are starting with a running `NixOS <https://nixos.org/>`_ system using the `defenestrate <https://git.m-labs.hk/M-Labs/defenestrate>`_ NixOS configuration for ARTIQ/Sinara. Notably, if you've recently ordered an ARTIQ/Sinara crate from M-Labs together with an accompanying preinstalled computer, **this will be how your machine is set up.** Welcome! What follows is a short guide to the configuration itself, how to adapt it to your needs, and how to work with Nix and NixOS in general.

.. tip::

   If you did not purchase a preinstalled computer from M-Labs, you can nonetheless reproduce the environment described here by installing NixOS and adopting the same configuration files. Specifically, the relevant files will be ``configuration.nix`` and ``flake.nix`` in the *defenestrate* repository linked above. See below for more information on different configuration files.

Getting started
---------------

Unless requested otherwise, ARTIQ NixOS machines ship with the desktop environment `GNOME <https://www.gnome.org/>`_, a popular choice across many Linux distributions. If you have used Linux before, you're likely already familiar with the interface. A set of basic desktop applications (Firefox, LibreOffice, Gimp) as well as some more specialized tools (Spyder, Jupyter, GTKWave, Wireshark) are also pre-installed and pre-configured. Later you will find that this list of installed packages is precisely specified in the ``configuration.nix`` file, and is very simple to edit to your needs.

.. note::
    You will find multiple preinstalled options for a terminal emulator, including XTerm and GNOME's Console. The configuration's default shell is the `friendly interactive shell <https://fishshell.com/>`_ or ``fish``. This handbook will assume you have a basic familiarity with a Linux environment and commands like ``sudo``, so if not, it's probably worth finding some materials on these things before you continue.

The hardware M-Labs ships for pre-installed ARTIQ machines is usually the `ASUS NUC 14RVK Pro Kit <https://www.asus.com/Websites/us/products/guxgpgyabgbrsz4o/pdf/6sa39dq3izs4int7.pdf>`_, with Intel i7-155H CPU, 32GB RAM, and a 1GB NVMe. Other options may also be available. Contact ``sales@`` for details.

Logging in
^^^^^^^^^^

The **default username** of the configuration is ``rabi`` (named after the physicist `Isidor Rabi <https://en.wikipedia.org/wiki/Isidor_Isaac_Rabi>`_.) The **default password** (also applicable for the root user) is ``rabi``. Initially, the system is configured for autologin and will not require a password for either login or use of ``sudo``.

Naturally, it's recommended to change this password immediately. You can use your preferred utility (e.g. the GNOME settings manager or the ``passwd`` command) to set a new password. You can also create new users as necessary. To turn off autologin, or require a password for ``sudo``, see below in :ref:`nixos-customizing`.

Using ARTIQ
^^^^^^^^^^^

The most recent release version of ARTIQ is already pre-installed on your machine, not through flakes or profiles (as described in :doc:`installing`) but in the NixOS configuration itself. Using ARTIQ is as simple as opening any terminal and typing any of the usual ARTIQ front-end or utility commands.

.. note::

    To flash a core device by JTAG, or connect to the UART log, note the USB I/O on the front of the ASUS NUC, and follow the instructions in :ref:`connecting-UART`. Pyserial and OpenOCD are pre-installed, and the default user is already included in the ``plugdev`` group.

Updating your system
^^^^^^^^^^^^^^^^^^^^

To update all software system-wide, it isn't necessary to directly edit any of the configuration files. Instead, you can use ``nix flake update``, e.g.: ::

    $ cd /etc/nixos
    $ sudo nix flake update

and build a new *generation*: ::

    $ sudo nixos-rebuild boot

A reboot will be required for changes to take effect. See below to learn more about generations.

In order to update to a **new release version of ARTIQ** (or to the beta) system-wide, first change the source used in ``flake.nix``: ::

    inputs.artiq.url = git+https://github.com/m-labs/artiq.git?ref=release-<number>;

(Remove ``?ref=release-<number>`` entirely for the beta branch). Then update and rebuild as above. Note however that ``sudo nix flake update`` and a rebuild will be required every time to incorporate new commits, and for easy access to the beta it may be better to use a flake, as described in :doc:`installing`.

.. tip::

    The ``inputs.artiq.url`` key can also be replaced with a path to a local clone of the ARTIQ repository on your system, e.g.: ::

        path:/absolute/path/to/your/ARTIQ

    if you'd like to be able to edit the source for your system-wide installation. Again, however, for such purposes it may be better to use flakes, rather than requiring a full rebuild for each update.

Nix and declarative configuration
---------------------------------

Before you start customizing your configuration, it may be useful to take some time to understand why NixOS functions the way it does. The central concept which makes Nix different from most package managers, and NixOS from most Linux distributions, is a *declarative* philosophy of package and environment management. In practice, what this means is that rather than simply installing packages into your system, you *define upfront* the list of packages available in your environment (or for particular, specialized environments) in a centralized configuration file. Nix then evaluates those configuration files to see what packages it should *make* available in specific contexts.

Since Nix goes to considerable lengths to build packages in isolation from each other, and to specify precisely the versions used in any given environment or build, this means, first of all, that environments are (almost) perfectly replicable. It's always possible to recreate, for example, your user environment, or the ARTIQ development environment, in any other context, simply by copying or referencing the files which declare them. Isolation means installed packages can't 'clutter up' your system, and can always be removed or upgraded independently without affecting each other.

Finally, reproducibility also applies to your *past* configurations. That is, as long as you save your previous configuration files, Nix allows for 'perfect' rollback. If you make changes that break your system, you can always revert to an older configuration, and you'll be able to return to precisely the environment you had before you made changes.

NixOS configuration files
^^^^^^^^^^^^^^^^^^^^^^^^^

Your system-wide configuration files are stored in ``/etc/nixos``. Because the *defenestrate* configuration uses `flakes <https://nixos.wiki/wiki/flakes>`_, there will be three files: ``hardware-configuration.nix``, ``flake.nix``, and ``configuration.nix``.

The first, ``hardware-configuration.nix``, is automatically generated by analyzing the actual hardware of the machine your NixOS is running. This is normally the only file which will differ if you choose to run the same NixOS configuration on different physical machines. Generally speaking, you shouldn't touch this file at all, unless you know what you're doing.

The second, ``flake.nix``, is the root of the configuration. In *defenestrate*, it notably configures the URL for the ARTIQ repository.

The third, ``configuration.nix``, is the usual configuration file for all NixOS variants. This is where most of the relevant settings for your environment are defined, including installed software.

.. note::

    The ``hardware-configuration.nix`` file is usually generated, along with a mostly-blank ``configuration.nix``, using the command ``nixos-generate-config``. Generally this is done during installation, but in some situations, especially if you change your partitioning scheme, it's recommended to regenerate it rather than editing it manually. To look over the output that would be generated without actually changing any files, use: ::

        $ nixos-generate-config --show-hardware-config

Generations and rollback
^^^^^^^^^^^^^^^^^^^^^^^^

In order to change your configuration, simply editing ``configuration.nix`` is not enough. Once you're satisfied with your changes, it's necessary to *trigger a rebuild*, which creates a new 'generation', i.e., a new iterated version of your personal NixOS. Notably, when you boot your machine, you'll notice that the ``systemd-boot`` bootloader offers you a choice between all your saved generations before starting the operating system.

.. tip::

    The ``systemd`` boot menu appears automatically for several seconds upon startup, but will relatively quickly continue with the default choice if not instructed otherwise. To prolong the time to make a choice, hit any arrow key and the timer will stop. Use arrow keys to make a selection and ``ENTER`` to continue.

To create a new generation, it's recommended to use the following command: ::

    $ sudo nixos-rebuild boot

This will build the new generation *and* set it as default in the bootloader, but not activate it (switch into it) immediately. This is somewhat preferable for stability reasons. There are other options, including ``nixos-rebuild switch``, which activates the new generation immediately (though some settings will still require a reboot to take effect), and ``nixos-rebuild test``, which generates and activates a rebuild but doesn't set it as default. See ``nixos-rebuild --help`` for more.

To rollback to an old generation, simply select it in the boot menu and boot into it.

.. warning::

    Like most Nix artifacts, old generations will be saved indefinitely unless garbage collected manually. On the other hand, if you run garbage collection regularly, old generations will also be deleted. See :ref:`nix-collect-garbage`.

Declarative vs. imperative
^^^^^^^^^^^^^^^^^^^^^^^^^^

As a further feature of NixOS's style of system management, it's useful to understand that a declarative configuration doesn't necessarily make it impossible to change elements of your system imperatively, i.e., conventionally.

Generally this is allowed purposefully. For example, in *defenestrate*, for ease of use, the ``mutableUsers`` option in ``configuration.nix`` is set to ``true``; this means that passwords, groups, and additional users are all imperatively manageable, and the settings changed will be preserved across generation rebuilds. There are also many common system settings, such as network connections, available keyboard layouts, and aesthetic features like desktop backgrounds, which *can* be managed declaratively -- in fact almost everything can be -- but are usually left to conventional settings managers (e.g. GNOME Settings), which operate imperatively.

Normally, these imperative settings will carry across seamlessly to newly built generations, since they are stored on your disk, in exactly the way you are probably used to. On the other hand, they will **not** transfer if you rebuild your configuration on a different machine, and they also can't be rolled back through Nix.

.. warning::
    Generally speaking, declarative configurations will overwrite imperative configurations upon a rebuild. For example, if you set ``mutableUsers`` to ``false`` in order to define users purely declaratively, the imperatively defined user list will be overwritten, and will not be retrievable by booting into an earlier generation.

.. _nixos-customizing:

Customizing your configuration
------------------------------

To customize your configuration, open ``configuration.nix`` in the editor of your choice. For changes to take effect, run ``sudo nixos-rebuild boot`` and reboot, as described above.

Note that ``configuration.nix`` is written in the *Nix language*, just as flakes are. You may therefore run into evaluation errors when rebuilding if you've misused the syntax. For relatively simple changes, the error messages should help you along; if you're interested in making more complex changes, you'll want to look into Nix itself. See also :ref:`nixos-further` below.

For all ``configuration.nix`` options and their effects, see the `list of options <https://nixos.org/manual/nixos/stable/options.html>`_ in the official NixOS manual. (This list is very long, and not worth reading through in its entirety. Use ``CTRL+F`` to search for specific options).

Basic settings
^^^^^^^^^^^^^^

Some basic settings should be immediately readable, such as timezone, host name, default locale, default key layout, and so on. If you ordered your machine from M-Labs, they will likely already be adapted to your requests, but you can also find them in ``configuration.nix``, under the following names: ::

    networking.hostName = "artiq";

    console.font = "Lat2-Terminus16";
    console.keyMap = "us";
    i18n.defaultLocale = "en_US.UTF-8";

    time.timeZone = "UTC";

(not necessarily in this order, or this proximity -- the order in which options are defined is arbitrary, and makes no difference to the system).

User management and login
^^^^^^^^^^^^^^^^^^^^^^^^^

Autologin is defined via the following options: ::

  services.displayManager.autoLogin.enable = true;
  services.displayManager.autoLogin.user = "rabi";

Set ``enable`` to ``false`` or delete both lines to disable autologin.

To change the behavior of ``sudo``, use the following option: ::

    security.sudo.wheelNeedsPassword = false;

Setting it to ``true`` will require a password for use of ``sudo``. The default password for root is also ``rabi``. The default username can also be changed by editing the relevant options. Other changes (new users, etc.) can safely be made imperatively.

.. seealso::

    Alternatively, you may choose to do all your user management declaratively. See `User Management <https://nixos.org/manual/nixos/stable/#sec-user-management>`_ in the NixOS manual.

You may also be interested in changing the default user shell, if you prefer a particular alternative to ``fish``. This is done with the ``users.defaultUserShell`` option.

Installing additional packages
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Broadly speaking, the software available in your system is supplied via a list assigned to a single option, ``environment.systemPackages``. A simple example may look like: ::

    environment.systemPackages = with pkgs; [
        vim
        wget
        gitAndTools.gitFull
        firefox
        gnome3.gnome-tweaks
        libreoffice-fresh
        vscodium
    ];

.. note::

    ``with pkgs`` is a convenience of the Nix language signifying that all these packages originate in the ``pkgs`` input, which is here specified in ``flake.nix`` as: ::

        inputs.nixpkgs.url = github:NixOS/nixpkgs/nixos-24.05;

    i.e. the central Nixpkgs repository for all Nix packages. Without ``with pkgs`` the list would have to be given as ``pkgs.wget``, ``pkgs.vim``, ``pkgs.gitAndTools.gitFull``, and so on.

To find out what packages are available, you can use `Nixpkgs search <https://search.nixos.org/packages>`_ in your browser. To install it in your environment, simply add the name of the package to the ``systemPackages`` list and rebuild. You can always test the package in your system first by obtaining packages ad-hoc with ``nix-shell``; see below.

Rarely, some software may require additional options to be set in order to function as expected. In particular, if a service or daemon needs to be configured, or if additional permissions or groups are necessary, it's often the case that the corresponding NixOS module needs to be enabled. For example: ::

    services.openssh.enable = true;

both installs the ``openssh`` package and configures and starts the ``sshd`` service.

Nix and NixOS tips
------------------

Installing additional packages (ad-hoc)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Often you might find yourself wanting access to a tool or a piece of software for a single use case or a limited time, without really wanting to install it into your system permanently. Nix provides a very convenient solution for this. Any package in the `Nixpkgs repository <https://search.nixos.org/packages>`_ can be installed temporarily, into a particular shell, with the command: ::

    $ nix-shell -p <pkg-name>

.. warning::

    Somewhat unfortunately, the two commands ``nix-shell`` and ``nix shell`` both exist in NixOS and **are not synonymous**. Note in this case the use of the hyphen. To start a shell from a *flake*, use ``nix shell`` with no hyphen. A similar distinction applies for ``nix-build`` and ``nix build``.

Much as with flakes, the command may take some time at first use for large packages, but if you end up calling repeatedly, subsequent invocations will reference the Nix store and run almost instantly. Also much as with flakes, the package is not 'installed' in a permanent sense and will disappear once the shell is closed. This is also useful in order to be able to test packages quickly before installing them into the environment.

Flakes and builds
^^^^^^^^^^^^^^^^^

Running NixOS is perfectly compatible with the other Nix features used by ARTIQ. In particular, using ``nix shell`` or ``nix develop`` with the various ARTIQ flakes, as described in :doc:`installing` and :doc:`flashing`, can continue to be very useful, especially to access different versions of ARTIQ, even simultaneously. It is also perfectly possible to install packages into your Nix profile. All of these are ways to define and make use of certain environments, with access to certain sets of packages, none of which will overwrite each other.

Note that, for instance, if you have installed ARTIQ ``release-8`` into your environment, but run ``nix shell`` on the ARTIQ ``release-7`` flake, that *specific shell* will run ``release-7`` commands, whereas all others will continue to use the system default environment, with ``release-8``. You can check this kind of behavior yourself with ``--version``.

.. _nix-collect-garbage :

Garbage collection
^^^^^^^^^^^^^^^^^^

As also noted in :doc:`installing`, Nix stores all packages it encounters in ``/nix/store``, which generally ensures that any given version of a package only needs to be fetched and built once, even when reused repeatedly or in different environments. Old NixOS generations are also stored, and will remain available in the boot menu upon future boots. With time, however, this can start to occupy large amounts of storage space. To clear out the Nix store and free up more space, run: ::

    $ sudo nix-collect-garbage

To clear old generations, it's also necessary to run: ::

    $ sudo nix-collect-garbage --delete-old

If you'd like to preserve the possibility of rollback, one option is to use ``--delete-older-than``, for example: ::

    $ sudo nix-collect-garbage --delete-older-than=30d

which will only delete generations older than thirty days. To save configurations in a more permanent way, you can save old versions of ``configuration.nix``, ``flake.nix``, and ``flake.lock``.

.. _nixos-further:

Further resources
^^^^^^^^^^^^^^^^^

- The `Nix package lookup <https://search.nixos.org/packages>`_
- The `NixOS manual <https://nixos.org/manual/nixos/stable/>`_, in particular the `list of configuration options <https://nixos.org/manual/nixos/stable/options.html>`_
- If you are interested in learning to use itself Nix in more detail, `nix.dev <https://nix.dev/tutorials/>`_ and `noogle <https://noogle.dev/>`_
- Various official NixOS sources, including an `official wiki <https://wiki.nixos.org/wiki/NixOS_Wiki>`_
