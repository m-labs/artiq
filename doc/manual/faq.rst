FAQ (How do I...)
=================

use this documentation?
-----------------------

The content of this manual is arranged in rough reading order. If you start at the beginning and make your way through section by section, you should form a pretty good idea of how ARTIQ works and how to use it. Otherwise:

**If you are just starting out,** and would like to get ARTIQ set up on your computer and your core device, start with :doc:`installing`, :doc:`flashing`, and :doc:`configuring`, in that order.

**If you have a working ARTIQ setup** (or someone else has set it up for you), start with the tutorials: read :doc:`rtio`, then progress to :doc:`getting_started_core` and :doc:`getting_started_mgmt`. If your system is in a DRTIO configuration, :doc:`DRTIO and subkernels <using_drtio_subkernels>` will also be helpful.

Pages like :doc:`management_system` and :doc:`core_device` describe **specific components of the ARTIQ ecosystem** in more detail. If you want to understand more about device and dataset databases, for example, read the :doc:`environment` page; if you want to understand the ARTIQ Python dialect and everything it does or does not support, read the :doc:`compiler` page.

Reference pages, like :doc:`main_frontend_tools` and :doc:`core_drivers_reference`, contain the detailed documentation of the individual methods and command-line tools ARTIQ provides. They are heavily interlinked throughout the rest of the documentation: whenever a method, tool, or exception is mentioned by name, like :class:`~artiq.frontend.artiq_run`, :meth:`~artiq.language.core.now_mu`, or :exc:`~artiq.coredevice.exceptions.RTIOUnderflow`, it can normally be clicked on to directly access the reference material. Notice also that the online version of this manual is searchable; see the 'Search docs' bar at left.

.. _build-documentation:

build this documentation?
-------------------------

To generate this manual from source, you can use ``nix build`` directives, for example: ::

    $ nix build git+https://github.com/m-labs/artiq.git\?ref=release-[number]#artiq-manual-html

Substitute ``artiq-manual-pdf`` to get the LaTeX PDF version. The results will be in ``result``.

The manual is written in `reStructured Text <https://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html>`_; you can find the source files in the ARTIQ repository under ``doc/manual``. If you spot a mistake, a typo, or something that's out of date or missing -- in particular, if you want to add something to this FAQ -- feel free to clone the repository, edit the source RST files, and make a pull request with your version of an improvement. (If you're not a fan of or not familiar with command-line Git, both GitHub and Gitea support making edits and pull requests directly in the web interface; tutorial materials are easy to find online.) The second best thing is to open an issue to make M-Labs aware of the problem.

.. _faq-find-examples:

find ARTIQ examples?
--------------------

The official examples are stored in the ``examples`` folder of the ARTIQ package. You can find the location of the ARTIQ package on your machine with: ::

  python3 -c "import artiq; print(artiq.__path__[0])"

Copy the ``examples`` folder from that path into your home or user directory, and start experimenting!

If you have progressed past this level and would like to see more in-depth code or real-life examples of how other groups have handled running experiments with ARTIQ, see the "Community code" directory on the M-labs `resources page <https://m-labs.hk/experiment-control/resources/>`_.

fix 'no startup kernel found' / 'no idle kernel found' in the UART?
-------------------------------------------------------------------

Don't. Note that these are ``INFO`` messages, and not ``ERROR`` or even ``WARN``. If you haven't flashed an idle or startup kernel yet, this is normal, and will not cause any problems; between experiments the core device will simply do nothing. The same applies to most other messages in the style of 'no configuration found' or 'falling back to default'. Your system will generally run just fine on its defaults until you get around to setting these configurations, though certain features may be limited until properly set up. See :doc:`configuring` and the list of keys in :ref:`core-device-flash-storage`.

fix 'Mismatch between gateware and software versions'?
------------------------------------------------------

Either reflash your core device with a newer version of ARTIQ (see :doc:`flashing`) or update your software (see :ref:`installing-upgrading`), depending on which is out of date.

.. note::
    You can check the specific versions you are using at any time by comparing the gateware version given in the core startup log and the output given by adding ``--version`` to any of the standard ARTIQ front-end commands. This is especially useful when e.g. seeking help in the forum or helpdesk@, where your running ARTIQ version is often crucial information to diagnose a problem.

    Minor version mismatches are common, even in stable ARTIQ versions, but should not cause any issues. The ARTIQ release system ensures breaking changes are strictly limited to new release versions, or to the beta branch (which explicitly makes no promises of stability.) Updates that *are* applied to the stable version are usually bug fixes, documentation improvements, or other quality-of-life changes. As long as gateware and software are using the same stable release version of ARTIQ, even if there is a minor mismatch, no warning will be displayed.

change configuration settings of satellite devices?
---------------------------------------------------

Currently, it is not possible to reach satellites through ``artiq_coremgmt config``, although this is being worked on. On Kasli, use :class:`~artiq.frontend.artiq_mkfs` and :class:`~artiq.frontend.artiq_flash`; on Kasli-SoC, preload the SD card with a ``config.txt``, formatted as a list of ``key=value`` pairs, one per line.

Don't worry about individually flashing idle or startup kernels. If your idle or startup kernel contains subkernels, it will automatically compile as a ``.tar``, which you only need to flash to the master.

.. _faq-networking:

troubleshoot networking problems?
---------------------------------

Diagnosis aids:

    - Can you ``ping`` the device?
    - Is the Ethernet LED on?
    - Is the ERROR LED on?
    - Is there anything unusual recorded in :ref:`the UART log <connecting-UART>`?

Some things to consider:

    - Is the ``core_addr`` field of your ``device_db.py`` set correctly?
    - Are your core device's IP address and networking configurations definitely set correctly? Check the UART log for evidence of this, and talk to your network administrator about what the correct choices are.
    - Is your core device configured for an external reference clock? If so, it cannot function correctly without one. Is the external reference clock plugged in?
    - Are Ethernet and (on Kasli only) SFP0 plugged in all the way? Are they working? Try different cables and SFP adapters; M-Labs tests with CAT6 cables, but lower categories should be supported too.
    - Are your PC and your crate in the same subnet?
    - Is some other device in your network already using the configured IP address? Turn off the core device and try pinging the configured IP address; if it responds, you have a culprit. One of the two will need a different networking configuration.
    - Are there restrictions or issues in your router or subnet that are preventing the core device from connecting? It may help to try connecting the core device to your PC directly.

diagnose and fix sequence errors?
---------------------------------

Go through your code, keeping manual track of SED lanes. See the following example: ::

    @kernel
    def run(self):
        self.core.reset()
        with parallel:
            self.ttl0.on()  # lane0
            self.ttl_sma.pulse(800*us)  # lane1(rising) lane1(falling)
            with sequential:
                self.ttl1.on()  # lane2
                self.ttl2.on()  # lane3
                self.ttl3.on()  # lane4
                self.ttl4.on()  # lane5
                delay(800*us)
                self.ttl1.off() # lane5
                self.ttl2.off() # lane6
                self.ttl3.off() # lane7
                self.ttl4.off() # lane0
        self.ttl0.off()  # lane1 -> clashes with the falling edge of ttl_sma,
                         # which is already at +800us

In most cases, as in this one, it's relatively easy to rearrange the generation of events so that they will be better spread out across SED lanes without sacrificing actual functionality. One possible solution for the above sequence looks like: ::

    @kernel
    def run(self):
        self.core.reset()
        self.ttl0.on()     # lane0
        self.ttl_sma.on()  # lane1
        self.ttl1.on()     # lane2
        self.ttl2.on()     # lane3
        self.ttl3.on()     # lane4
        self.ttl4.on()     # lane5
        delay(800*us)
        self.ttl1.off()    # lane5
        self.ttl2.off()    # lane6
        self.ttl3.off()    # lane7
        self.ttl4.off()    # lane0  (no clash: new timestamp is higher than last)
        self.ttl_sma.off() # lane1
        self.ttl0.off()    # lane2

In this case, the :meth:`~artiq.coredevice.ttl.TTLInOut.pulse` is split up into its component :meth:`~artiq.coredevice.ttl.TTLInOut.on` and  :meth:`~artiq.coredevice.ttl.TTLInOut.off` so that events can be generated more linearly. It can also be worth keeping in mind that delaying by even a single coarse RTIO cycle between events avoids switching SED lanes at all; in contexts where perfect simultaneity is not a priority, this is an easy way to avoid sequencing issues. See again :ref:`sequence-errors`.

organize datasets in folders?
-----------------------------

Use the dot (".") in dataset names to separate folders. The GUI will automatically create and delete folders in the dataset tree display.

organize experiment windows in the dashboard?
---------------------------------------------

Experiment windows can be organized by using the following hotkeys:

* CTRL+SHIFT+T to tile experiment windows
* CTRL+SHIFT+C to cascade experiment windows

The windows will be organized in the order they were last interacted with.

create and use variable-length arrays in kernels?
-------------------------------------------------

You can't, in general; see the corresponding notes under :ref:`compiler-types`. ARTIQ kernels do not support heap allocation, meaning in particular that lists, arrays, and strings must be of constant size. One option is to preallocate everything, as mentioned on the Compiler page; another option is to chunk it and e.g. read 100 events per function call, push them upstream and retry until the gate time closes.

write part of my experiment as a coroutine/asyncio task/generator?
------------------------------------------------------------------

You cannot change the API that your experiment exposes: :meth:`~artiq.language.environment.HasEnvironment.build`, :meth:`~artiq.language.environment.Experiment.prepare`, :meth:`~artiq.language.environment.Experiment.run` and :meth:`~artiq.language.environment.Experiment.analyze` need to be regular functions, not generators or asyncio coroutines. That would make reusing your own code in sub-experiments difficult and fragile. You can however wrap your own generators/coroutines/tasks in regular functions that you then expose as part of the API.

determine the pyserial URL to connect to a device by its serial number?
-----------------------------------------------------------------------

You can list your system's serial devices and print their vendor/product id and serial number by running::

    $ python3 -m serial.tools.list_ports -v

This will give you the ``/dev/ttyUSBxx`` (or ``COMxx`` for Windows) device names. The ``hwid:`` field gives you the string you can pass via the ``hwgrep://`` feature of pyserial `serial_for_url() <https://pythonhosted.org/pyserial/pyserial_api.html#serial.serial_for_url>`_ in order to open a serial device.

The preferred way to specify a serial device is to make use of the ``hwgrep://`` URL: it allows for selecting the serial device by its USB vendor ID, product
ID and/or serial number. These never change, unlike the device file name.

For instance, if you want to specify the Vendor/Product ID and the USB Serial Number, you can do: ::

    $ -d "hwgrep://<VID>:<PID> SNR=<serial_number>"``.

run unit tests?
---------------

The unit tests assume that the Python environment has been set up in such a way that ``import artiq`` will import the code being tested, and that this is still true for any subprocess created. This is not the way setuptools operates as it adds the path to ARTIQ to ``sys.path`` which is not passed to subprocesses; as a result, running the tests via ``setup.py`` is not supported. The user must first install the package or set ``PYTHONPATH``, and then run the tests with e.g. ``python3 -m unittest discover`` in the ``artiq/test`` folder and ``lit .`` in the ``artiq/test/lit`` folder.

For the hardware-in-the-loop unit tests, set the ``ARTIQ_ROOT`` environment variable to the path to a device database containing the relevant devices.

The core device tests require the following TTL devices and connections:

* ``ttl_out``: any output-only TTL.
* ``ttl_out_serdes``: any output-only TTL that uses a SERDES (i.e. has a fine timestamp). Can be aliased to ``ttl_out``.
* ``loop_out``: any output-only TTL. Must be physically connected to ``loop_in``. Can be aliased to ``ttl_out``.
* ``loop_in``: any input-capable TTL. Must be physically connected to ``loop_out``.
* ``loop_clock_out``: a clock generator TTL. Must be physically connected to ``loop_clock_in``.
* ``loop_clock_in``: any input-capable TTL. Must be physically connected to ``loop_clock_out``.

If TTL devices are missing, the corresponding tests are skipped.

find the dashboard and browser configuration files?
---------------------------------------------------

::

  python -c "from artiq.tools import get_user_config_dir; print(get_user_config_dir())"

Additional Resources
====================

Other related documentation
---------------------------

- the `Sinara wiki <https://github.com/sinara-hw/meta/wiki>`_
- the `SiPyCo manual <https://m-labs.hk/artiq/sipyco-manual/>`_
- the `Migen manual <https://m-labs.hk/migen/manual/>`_
- in a pinch, the `M-labs internal docs <https://git.m-labs.hk/sinara-hw/assembly>`_

For more advanced questions, sometimes the `list of publications <https://m-labs.hk/experiment-control/publications/>`_ about experiments performed using ARTIQ may be interesting. See also the official M-Labs `resources <https://m-labs.hk/experiment-control/resources/>`_ page, especially the section on community code.

"Help, I've done my best and I can't get any further!"
------------------------------------------------------

- If you have an active M-Labs AFWS/support subscription, you can email helpdesk@ at any time for personalized assistance.
- Compare your materials with the examples; see also :ref:`finding ARTIQ examples <faq-find-examples>` above.
- Check the list of `active issues <https://github.com/m-labs/artiq/issues>`_ on the ARTIQ GitHub repository for possible known problems with ARTIQ. Search through the closed issues to see if your question or concern has been addressed before.
- Search the `M-Labs forum <https://forum.m-labs.hk/>`_ for similar problems, or make a post asking for help yourself.
- Look into the `Mattermost live chat <https://chat.m-labs.hk>`_ or the bridged IRC channel.
- Read the open source code and its docstrings and figure it out.
- If you're reasonably certain you've identified a bug, or if you'd like to suggest a feature that should be included in future ARTIQ releases, `file a GitHub issue <https://github.com/m-labs/artiq/issues/new/choose>`_ yourself, following one of the provided templates.
- In some odd cases, you may want to see the `mailing list archive <https://www.mail-archive.com/artiq@lists.m-labs.hk/>`_; the ARTIQ mailing list was shut down at the end of 2020 and was last regularly used during the time of ARTIQ-2 and 3, but for some older ARTIQ features, or to understand a development thought process, you may still find relevant information there.

In any situation, if you found the manual unclear or unhelpful, you might consider following the :ref:`directions for contribution <build-documentation>` and editing it to be more helpful for future readers.