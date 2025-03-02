Building and developing ARTIQ
=============================

.. warning::
    This section is only for software or FPGA developers who want to modify ARTIQ. The steps described here are not required if you simply want to run experiments with ARTIQ. If you purchased a system from M-Labs or QUARTIQ, we usually provide board binaries for you; you can use the AFWS client to get updated versions if necessary, as described in :ref:`obtaining-binaries`. It is not necessary to build them yourself.

The easiest way to obtain an ARTIQ development environment is via the `Nix package manager <https://nixos.org/nix/>`_ on Linux. The Nix system is used on the `M-Labs Hydra server <https://nixbld.m-labs.hk/>`_ to build ARTIQ and its dependencies continuously; it ensures that all build instructions are up-to-date and allows binary packages to be used on developers' machines, in particular for large tools such as the Rust compiler.

ARTIQ itself does not depend on Nix, and it is also possible to obtain everything from source (look into the ``flake.nix`` file to see what resources are used, and run the commands manually, adapting to your system) - but Nix makes the process a lot easier.

Installing Vivado
-----------------

It is necessary to independently install AMD's `Vivado <https://www.xilinx.com/support/download.html>`_, which requires a login for download and can't be automatically obtained by package managers. The "appropriate" Vivado version to use for building gateware and firmware can vary. Some versions contain bugs that lead to hidden or visible failures, others work fine. Refer to the ``flake.nix`` file from the ARTIQ repository in order to determine which version is used at M-Labs.

.. tip::
    Text-search ``flake.nix`` for a mention of ``/opt/Xilinx/Vivado``. Given e.g. the line ::

        profile = "set -e; source /opt/Xilinx/Vivado/2022.2/settings64.sh"

    the intended Vivado version is 2022.2.

Download and run the official installer. If using NixOS, note that this will require a FHS chroot environment; the ARTIQ flake provides such an environment, which you can enter with the command ``vivado-env`` from the development environment (i.e. after ``nix develop``). Other tips:

- Be aware that Vivado is notoriously not a lightweight piece of software and you will likely need **at least 70GB+** of free space to install it.
- If you do not want to write to ``/opt``, you can install into a folder of your home directory.
- During the Vivado installation, uncheck ``Install cable drivers`` (they are not required, as we use better open source alternatives).
- If the Vivado GUI installer crashes, you may be able to work around the problem by running it in unattended mode with a command such as ``./xsetup -a XilinxEULA,3rdPartyEULA,WebTalkTerms -b Install -e 'Vitis Unified Software Platform' -l /opt/Xilinx/``.
- Vivado installation issues are not uncommon. Searching for similar problems on `the M-Labs forum <https://forum.m-labs.hk/>`_ or `Vivado's own support forums <https://support.xilinx.com/s/topic/0TO2E000000YKXwWAO/installation-and-licensing>`_ might be helpful when looking for solutions.

.. _system-description:

System description file
-----------------------

ARTIQ gateware and firmware binaries are dependent on the system configuration. In other words, a specific set of ARTIQ binaries is bound to the exact arrangement of real-time hardware it was generated for: the core device itself, its role in a DRTIO context (master, satellite, or standalone), the (real-time) peripherals in use, the physical EEM ports they will be connected to, and various other basic specifications. This information is normally provided to the software in the form of a JSON file called the system description file.

.. warning::

    Not all core devices use system description files. Devices that use system description files for configuration are referred to as JSON variants (see :ref:`JSON variant devices <devices-table>`). Some rare or specialized boards use hardcoded variants, selected by a variant name such as ``nist_clock``, without needing a system description file (see :ref:`Hardcoded variant devices <devices-table>`). For the list of supported variants, see the :ref:`building` section. Writing new hardcoded variants is not a trivial task and is generally not recommended unless you are an experienced FPGA developer.

If you already have your system description file on hand, you can edit it to reflect any changes in configuration. If you purchased your original system from M-Labs, or recently purchased new hardware to add to it, you can obtain your up-to-date system description file through AFWS at any time using the command ``$ afws_client get_json`` (see :ref:`AFWS client<afws-client>`). If you are starting from scratch, a close reading of ``coredevice_generic.schema.json`` in ``artiq/coredevice`` will be helpful.

System descriptions do not need to be very complex. At its most basic, a system description looks something like: ::

    {
        "target": "kasli",
        "variant": "example",
        "hw_rev": "v2.0",
        "base": "master",
        "peripherals": [
            {
                "type": "grabber",
                "ports": [0]
            }
        ]
    }

Only these five fields are required, and the ``peripherals`` list can in principle be empty. A limited number of more extensive examples can currently be found in `the ARTIQ-Zynq repository <https://git.m-labs.hk/M-Labs/artiq-zynq/src/branch/master>`_, as well as in the main repository under ``artiq/examples/kasli_shuttler``. Once your system description file is complete, you can use ``artiq_ddb_template`` (see also :ref:`Utilities <ddb-template-tool>`) to test it and to generate a template for the corresponding :ref:`device database <device-db>`.

DRTIO descriptions
^^^^^^^^^^^^^^^^^^

Note that in DRTIO systems it is necessary to create one description file *per core device*. Satellites and their connected peripherals must be described separately. Satellites also need to be reflashed separately, albeit only if their personal system descriptions have changed. (The layout of satellites relative to the master is configurable on the fly and will be established much later, in the routing table; see :ref:`drtio-routing`. It is not necessary to rebuild or reflash if only changing the DRTIO routing table).

In contrast, only one device database should be generated even for a DRTIO system. Use a command of the form: ::

    $ artiq_ddb_template -s 1 <satellite1>.json -s 2 <satellite2>.json <master>.json

The numbers designate the respective satellite's destination number, which must correspond to the destination numbers used when generating the routing table later.

Common system description changes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To add or remove peripherals from the system, add or remove their entries from the ``peripherals`` field. When replacing hardware with upgraded versions, update the corresponding ``hw_rev`` (hardware revision) field. Other fields to consider include:

    - ``enable_wrpll`` (a simple boolean, see :ref:`core-device-clocking`)
    - ``sed_lanes`` (increasing the number of SED lanes can reduce sequence errors, but correspondingly consumes more FPGA resources, see :ref:`sequence-errors`)
    - various defaults (e.g. ``core_addr`` defines a default IP address, which can be freely reconfigured later).

Nix development environment
---------------------------

* Install `Nix <http://nixos.org/nix/>`_ if you haven't already. Prefer a single-user installation for simplicity.
* Configure Nix to support building ARTIQ:

    - Enable flakes, for example by adding ``experimental-features = nix-command flakes`` to ``nix.conf``. See also the `NixOS Wiki on flakes <https://nixos.wiki/wiki/flakes>`_.
    - Add ``/opt`` (or your Vivado location) as an Nix sandbox, for example by adding ``extra-sandbox-paths = /opt`` to ``nix.conf``.
    - Make sure that you have accepted and marked as permanent the additional settings described in :ref:`installing-details`. You can check on this manually by ensuring the file ``trusted-settings.json`` in ``~/.local/share/nix/`` exists and contains the following: ::

        {
            "extra-sandbox-paths":{
                "/opt":true
            },
            "extra-substituters":{
                "https://nixbld.m-labs.hk":true
            },
            "extra-trusted-public-keys":{
                "nixbld.m-labs.hk-1:5aSRVA5b320xbNvu30tqxVPXpld73bhtOeH6uAjRyHc=":true
            }
        }

    - If using NixOS, make the equivalent changes to your ``configuration.nix`` instead.

* Clone `the ARTIQ Git repository <https://github.com/m-labs/artiq>`_, or `the ARTIQ-Zynq repository <https://git.m-labs.hk/M-Labs/artiq-zynq>`__ for :ref:`Zynq devices <devices-table>` (Kasli-SoC, ZC706, or EBAZ4205). By default, you are working with the ``master`` branch, which represents the beta version and is not stable (see :doc:`releases`). Checkout the most recent release (``git checkout release-[number]``) for a stable version.
* If your Vivado installation is not in its default location ``/opt``, open ``flake.nix`` and edit it accordingly (note that the edits must be made in the main ARTIQ flake, even if you are working with Zynq, see also tip below).
* Run ``nix develop`` at the root of the repository, where ``flake.nix`` is.

.. note::
    You can also target legacy versions of ARTIQ; use Git to checkout older release branches. Note however that older releases of ARTIQ required different processes for developing and building, which you are broadly more likely to figure out by (also) consulting the corresponding older versions of the manual.

Once you have run ``nix develop`` you are in the ARTIQ development environment. All ARTIQ commands and utilities -- :mod:`~artiq.frontend.artiq_run`, :mod:`~artiq.frontend.artiq_master`, etc. -- should be available, as well as all the packages necessary to build or run ARTIQ itself. You can exit the environment at any time using Control+D or the ``exit`` command and re-enter it by re-running ``nix develop`` again in the same location.

.. tip::
    If you are developing for Zynq, you will have noted that the ARTIQ-Zynq repository consists largely of firmware. The firmware for Zynq (NAR3) is more modern than that used for current mainline ARTIQ, and is intended to eventually replace it; for now it constitutes most of the difference between the two ARTIQ variants. The gateware for Zynq, on the other hand, is largely imported from mainline ARTIQ.

    If you intend to modify the source housed in the original ARTIQ repository, but build and test the results on a Zynq device, clone both repositories and set your ``PYTHONPATH`` after entering the ARTIQ-Zynq development shell: ::

        $ export PYTHONPATH=/absolute/path/to/your/artiq:$PYTHONPATH

    Note that this only applies for incremental builds. If you want to use ``nix build``, or make changes to the dependencies, look into changing the inputs of the ``flake.nix`` instead. You can do this by replacing the URL of the GitHub ARTIQ repository with ``path:/absolute/path/to/your/artiq``; remember that Nix pins dependencies, so to incorporate new changes you will need to exit the development shell, update the environment with ``nix flake update``, and re-run ``nix develop``.

Building only standard binaries
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you are working with original ARTIQ, and you only want to build a set of standard binaries (i.e. without changing the source code), you can also enter the development shell without cloning the repository, using ``nix develop`` as follows: ::

    $ nix develop git+https://github.com/m-labs/artiq.git\?ref=release-[number]#boards

Leave off ``\?ref=release-[number]`` to prefer the current beta version instead of a numbered release.

.. note::
    Adding ``#boards`` makes use of the ARTIQ flake's provided ``artiq-boards-shell``, a lighter environment optimized for building firmware and flashing boards, which can also be accessed by running ``nix develop .#boards`` if you have already cloned the repository. Developers should be aware that in this shell the current copy of the ARTIQ sources is not added to your ``PYTHONPATH``. Run ``nix flake show`` and read ``flake.nix`` carefully to understand the different available shells.

The parallel command does exist for ARTIQ-Zynq: ::

    $ nix develop git+https://git.m-labs.hk/m-labs/artiq-zynq\?ref=release-[number]

but if you are building ARTIQ-Zynq without intention to change the source, it is not actually necessary to enter the development environment at all; Nix is capable of accessing the official flake directly to set up the build, eliminating the requirement for any particular environment.

This is equally possible for original ARTIQ, but not as useful, as the development environment (specifically the ``#boards`` shell) is still the easiest way to access the necessary tools for flashing the board. On the other hand, Zynq boards can also be flashed by writing to the SD card directly, which requires no further special tools. As long as you have a functioning Nix/Vivado installation with flakes enabled, you can progress directly to the building instructions below.

.. _building:

Building ARTIQ
--------------

For general troubleshooting and debugging, especially with a 'fresh' board, see also :ref:`connecting-uart`.

Kasli or KC705 (ARTIQ original)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

For Kasli, if you have your system description file on-hand, you can at this point build both firmware and gateware with a command of the form: ::

    $ python -m artiq.gateware.targets.kasli <description>.json

With KC705, use: ::

    $ python -m artiq.gateware.targets.kc705 -V <variant>

This will create a directory ``artiq_kasli`` or ``artiq_kc705`` containing the binaries in a subdirectory named after your description file or variant. Flash the board as described in :ref:`writing-flash`, adding the option ``--srcbuild``, e.g., assuming your board is connected by network or JTAG USB respectively: ::

    $ artiq_coremgmt flash --srcbuild artiq_<board>/<variant>
    $ artiq_flash --srcbuild [-t kc705] -d artiq_<board>/<variant>

.. note::
    To see supported KC705 variants, run: ::

        $ python -m artiq.gateware.targets.kc705 --help

    Look for the option ``-V VARIANT, --variant VARIANT``.

Kasli-SoC, ZC706 or EBAZ4205 (ARTIQ on Zynq)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The building process for :ref:`Zynq devices <devices-table>` is a little more complex. The easiest method is to leverage ``nix build`` and the ``makeArtiqZynqPackage`` utility provided by the official flake. The ensuing command is rather long, because it uses a multi-clause expression in the Nix language to describe the desired result; it can be executed piece-by-piece using the `Nix REPL <https://nix.dev/manual/nix/2.18/command-ref/new-cli/nix3-repl.html>`_, but ``nix build`` provides a lot of useful conveniences.

For Kasli-SoC, run: ::

    $ nix build --print-build-logs --impure --expr 'let fl = builtins.getFlake "git+https://git.m-labs.hk/m-labs/artiq-zynq?ref=release-[number]"; in (fl.makeArtiqZynqPackage {target="kasli_soc"; variant="<variant>"; json=<path/to/description.json>;}).kasli_soc-<variant>-sd'

Replace ``<variant>`` with ``master``, ``satellite``, or ``standalone``, depending on your targeted DRTIO role. Remove ``?ref=release-[number]`` to use the current beta version rather than a numbered release. If you have cloned the repository and prefer to use your local copy of the flake, replace the corresponding clause with ``builtins.getFlake "/absolute/path/to/your/artiq-zynq"``.

For ZC706 or EBAZ4205, you can use a command of the same form (replace ``<target>`` with ``zc706`` or ``ebaz4205``): ::

    $ nix build --print-build-logs --impure --expr 'let fl = builtins.getFlake "git+https://git.m-labs.hk/m-labs/artiq-zynq?ref=release-[number]"; in (fl.makeArtiqZynqPackage {target="<target>"; variant="<variant>";}).<target>-<variant>-sd'

or you can use the more direct version: ::

    $ nix build --print-build-logs git+https://git.m-labs.hk/m-labs/artiq-zynq\?ref=release-[number]#<target>-<variant>-sd

(which is possible for ZC706 and EBAZ4205 because there is no need to be able to specify a system description file in the arguments.)

.. note::
    To see supported variants for ZC705 or EBA4205, you can run the following at the root of the repository: ::

        $ src/gateware/<target>.py --help

    Look for the option ``-V VARIANT, --variant VARIANT``. If you have not cloned the repository or are not in the development environment, try: ::

        $ nix flake show git+https://git.m-labs.hk/m-labs/artiq-zynq\?ref=release-[number] | grep "package '<target>.*sd"

    to see the list of suitable build targets directly.

Any of these commands should produce a directory ``result`` which contains a file ``boot.bin``. If your core device is accessible by network, flash with: ::

    $ artiq_coremgmt flash result

Otherwise:

1. Power off the board, extract the SD card and load ``boot.bin`` onto it manually.
2. Insert the SD card back into the board.
3. Set to boot from SD card:

   - For Kasli-SoC or ZC706, ensure that the DIP switches (labeled BOOT MODE) are set correctly, to SD.
   - For EBAZ4205, set up the `boot select resistor <https://github.com/xjtuecho/EBAZ4205>`_ to boot from SD card.

4. Power the board back on.

Optionally, the SD card may also be loaded at the same time with an additional file ``config.txt``, which can contain preset configuration values in the format ``key=value``, one per line. The keys are those used with :mod:`~artiq.frontend.artiq_coremgmt`. This allows e.g. presetting an IP address and any other configuration information.

After a successful boot, the "FPGA DONE" light should be illuminated and the board should respond to ping when plugged into Ethernet.

.. _zynq-jtag-boot :

Booting over JTAG/Ethernet
""""""""""""""""""""""""""

It is also possible to boot :ref:`Zynq devices <devices-table>` over USB and Ethernet (EBAZ4205 not currently supported). Flip the DIP switches to JTAG. The scripts ``remote_run.sh`` and ``local_run.sh`` in the ARTIQ-Zynq repository, intended for use with a remote JTAG server or a local connection to the core device respectively, are used at M-Labs to accomplish this. Both make use of the netboot tool ``artiq_netboot``, see also its source `here <https://git.m-labs.hk/M-Labs/artiq-netboot>`__, which is included in the ARTIQ-Zynq development environment. Adapt the relevant script to your system or read it closely to understand the options and the commands being run; note for example that ``remote_run.sh`` as written only supports ZC706.

You will need to generate the gateware, firmware and bootloader first, either through ``nix build`` or incrementally as below. After an incremental build add the option ``-i`` when running either of the scripts. If using ``nix build``, note that target names of the form ``<board>-<variant>-jtag`` (run ``nix flake show`` to see all targets) will output the three necessary files without combining them into ``boot.bin``.

.. warning::

    A known Xilinx hardware bug on Zynq prevents repeatedly loading the SZL bootloader over JTAG (i.e. repeated calls of the ``*_run.sh`` scripts) without a POR reset. On Kasli-SoC, you can physically set a jumper on the ``PS_POR_B`` pins of your board and use the M-Labs `POR reset script <https://git.m-labs.hk/M-Labs/zynq-rs/src/branch/master/kasli_soc_por.py>`_.

Zynq incremental build
^^^^^^^^^^^^^^^^^^^^^^

The ``boot.bin`` file used in a Zynq SD card boot is in practice the combination of several files, normally ``top.bit`` (the gateware), ``runtime`` or ``satman`` (the firmware) and ``szl.elf`` (an open-source bootloader for Zynq `written by M-Labs <https://git.m-labs.hk/M-Labs/zynq-rs/src/branch/master/szl>`_, used in ARTIQ in place of Xilinx's FSBL). In some circumstances, especially if you are developing ARTIQ, you may prefer to construct these components separately. Be sure that you have cloned the repository and entered the development environment as described above.

To compile the gateware and firmware, enter the ``src`` directory and run two commands as follows:

For Kasli-SoC:
    ::

    $ gateware/kasli_soc.py -g ../build/gateware <description.json>
    $ make TARGET=kasli_soc GWARGS="path/to/description.json" <fw-type>

For ZC706 or EBAZ4205:
    ::

    $ gateware/<target>.py -g ../build/gateware -V <variant>
    $ make TARGET=<target> GWARGS="-V <variant>" <fw-type>

where ``fw-type`` is ``runtime`` for standalone or DRTIO master builds and ``satman`` for DRTIO satellites. Both the gateware and the firmware will generate into the ``../build`` destination directory. At this stage, if supported, you can :ref:`boot from JTAG <zynq-jtag-boot>`; either of the ``*_run.sh`` scripts will expect the gateware and firmware files at their default locations, and the ``szl.elf`` bootloader is retrieved automatically.

If you prefer to boot from SD card, you will need to construct your own ``boot.bin``. Build ``szl.elf`` from source by running a command of the form: ::

    $ nix build git+https://git.m-labs.hk/m-labs/zynq-rs#<board>-szl

For easiest access run this command in the ``build`` directory. The ``szl.elf`` file will be in the subdirectory ``result``. To combine all three files into the boot image, create a file called ``boot.bif`` in ``build`` with the following contents: ::

    the_ROM_image:
        {
            [bootloader]result/szl.elf
            gateware/top.bit
            firmware/armv7-none-eabihf/release/<fw-type>
        }
        EOF

Save this file. Now use ``mkbootimage`` to create ``boot.bin``. ::

$   mkbootimage boot.bif boot.bin

Boot from SD card as above.
