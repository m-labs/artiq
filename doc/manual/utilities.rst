Utilities
=========

.. Sort these tool by some subjective combination of their
   typical sequence and expected frequency of use.

.. As in main_frontend_reference, automodule directives display nothing and are here to make :mod: links possible

.. _afws-client:

ARTIQ Firmware Service (AFWS) client
------------------------------------

.. automodule:: artiq.frontend.afws_client

This tool serves as a client for building tailored firmware and gateware from M-Lab's servers and downloading the binaries in ready-to-flash format. It is necessary to have a valid subscription to AFWS to use it. Subscription also includes general helpdesk support and can be purchased or extended by contacting ``sales@``. One year of support is included with any Kasli carriers or crates containing them purchased from M-Labs. Additional one-time use is generally provided with purchase of additional cards to facilitate the system configuration change.

.. argparse::
   :ref: artiq.frontend.afws_client.get_argparser
   :prog: afws_client
   :nodescription:
   :nodefault:

   passwd
      .. warning::
         After receiving your credentials from M-Labs, it is recommended to change your password as soon as possible. It is your responsibility to set and remember a secure password. If necessary, passwords can be reset by contacting helpdesk@.

Static compiler
---------------

.. automodule:: artiq.frontend.artiq_compile

Compiles an experiment into a ELF file (or a TAR file if the experiment involves subkernels). It is primarily used to prepare binaries for the startup and idle kernels, loaded in non-volatile storage of the core device. Experiments compiled with this tool are not allowed to use RPCs, and their ``run`` entry point must be a kernel.

.. argparse::
   :ref: artiq.frontend.artiq_compile.get_argparser
   :prog: artiq_compile
   :nodescription:
   :nodefault:

Flash storage image generator
-----------------------------

.. automodule:: artiq.frontend.artiq_mkfs

Compiles key/value pairs (e.g. configuration information) into a binary image suitable for flashing into the storage space of the core device. It can be used in combination with ``artiq_flash`` to configure the core device, but this is normally necessary at most to set the ``ip`` field; once the core device is reachable by network it is preferable to use ``artiq_coremgmt config``. Not applicable to ARTIQ-Zynq, where preconfiguration is better achieved by loading ``config.txt`` onto the SD card.

.. argparse::
   :ref: artiq.frontend.artiq_mkfs.get_argparser
   :prog: artiq_mkfs
   :nodescription:
   :nodefault:

.. _flashing-loading-tool:

Flashing/Loading tool
---------------------

.. automodule:: artiq.frontend.artiq_flash

Allows for flashing and loading of various files onto the core device. Not applicable to ARTIQ-Zynq, where gateware and firmware should be loaded onto the core device with :mod:`~artiq.frontend.artiq_coremgmt`, directly copied onto the SD card, or (for developers) using the :ref:`ARTIQ netboot <zynq-jtag-boot>` utility.

.. argparse::
   :ref: artiq.frontend.artiq_flash.get_argparser
   :prog: artiq_flash
   :nodescription:
   :nodefault:

.. _core-device-management-tool:

Core device management tool
---------------------------

.. automodule:: artiq.frontend.artiq_coremgmt

The core management utility gives remote access to the core device logs, the :ref:`core device flash storage <configuration-storage>`, and other management functions.

To use this tool, it is necessary to specify the IP address your core device can be contacted at. If no option is used, the utility will assume there is a file named ``device_db.py`` in the current directory containing the :ref:`device database <device-db>`; otherwise, a device database file can be provided with ``--device-db`` or an address directly with ``--device`` (see also below).

.. argparse::
   :ref: artiq.frontend.artiq_coremgmt.get_argparser
   :prog: artiq_coremgmt
   :nodescription:
   :nodefault:

.. _ddb-template-tool:

Device database template generator
----------------------------------

.. automodule:: artiq.frontend.artiq_ddb_template

This tool generates a basic template for a :ref:`device database <device-db>` given the JSON description file(s) for the system. Entries for :ref:`controllers <environment-ctlrs>` are not generated.

.. argparse::
   :ref: artiq.frontend.artiq_ddb_template.get_argparser
   :prog: artiq_ddb_template
   :nodescription:
   :nodefault:

.. _rtiomap-tool:

RTIO channel name map tool
--------------------------

.. automodule:: artiq.frontend.artiq_rtiomap

This tool encodes the map of RTIO channel numbers to names in a format suitable for writing to the config key ``device_map``. See :ref:`config-rtiomap`.

.. argparse::
   :ref: artiq.frontend.artiq_rtiomap.get_argparser
   :prog: artiq_rtiomap
   :nodescription:
   :nodefault:

Core device RTIO analyzer tool
------------------------------

.. automodule:: artiq.frontend.artiq_coreanalyzer

This tool retrieves core device RTIO logs either as raw data or as VCD waveform files, which are readable by third-party tools such as GtkWave. See :ref:`rtio-analyzer` for an example, or :mod:`artiq.test.coredevice.test_analyzer` for a relevant unit test.

Using the management system, the respective functionality is provided by :mod:`~artiq.frontend.aqctl_coreanalyzer_proxy` and the dashboard's 'Waveform' tab; see :ref:`interactivity-waveform`.

.. argparse::
   :ref: artiq.frontend.artiq_coreanalyzer.get_argparser
   :prog: artiq_coreanalyzer
   :nodescription:
   :nodefault:

.. _routing-table-tool:

DRTIO routing table manipulation tool
-------------------------------------

.. automodule:: artiq.frontend.artiq_route

This tool allows for manipulation of a DRTIO routing table file, which can be transmitted to the core device using :mod:`artiq_coremgmt config write<artiq.frontend.artiq_coremgmt>`; see :ref:`drtio-routing`.

.. argparse::
   :ref: artiq.frontend.artiq_route.get_argparser
   :prog: artiq_route
   :nodescription:
   :nodefault:

ARTIQ RTIO monitor
------------------

.. automodule:: artiq.frontend.artiq_rtiomon

Command-line interface for monitoring RTIO channels, as in the Monitor capacity of dashboard MonInj. See :ref:`interactivity-moninj`.

.. argparse::
   :ref: artiq.frontend.artiq_rtiomon.get_argparser
   :prog: artiq_rtiomon
   :nodescription:
   :nodefault:

.. _utilities-ctrls:

MonInj proxy
------------

.. automodule:: artiq.frontend.aqctl_moninj_proxy

.. argparse::
   :ref: artiq.frontend.aqctl_moninj_proxy.get_argparser
   :prog: aqctl_moninj_proxy
   :nodefault:

Core device RTIO analyzer proxy
-------------------------------

.. automodule:: artiq.frontend.aqctl_coreanalyzer_proxy

.. argparse::
   :ref: artiq.frontend.aqctl_coreanalyzer_proxy.get_argparser
   :prog: aqctl_coreanalyzer_proxy
   :nodefault:

Core device logging controller
------------------------------

.. automodule:: artiq.frontend.aqctl_corelog

.. argparse::
   :ref: artiq.frontend.aqctl_corelog.get_argparser
   :prog: aqctl_corelog
   :nodefault: