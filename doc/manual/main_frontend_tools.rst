Main front-end tools
====================

These are the top-level commands used to run and manage ARTIQ experiments. Not all of the ARTIQ front-end is described here (many additional useful commands are presented in this manual in :doc:`utilities`) but these together comprise the main points of access for using ARTIQ as a system.

.. Note that ARTIQ frontend has no docstrings and the ..automodule directives display nothing; they are there to make :mod: references function correctly, since sphinx-argparse does not support links to ..argparse directives in the same way.

:mod:`artiq.frontend.artiq_run`
-------------------------------

.. automodule:: artiq.frontend.artiq_run
.. argparse::
   :ref: artiq.frontend.artiq_run.get_argparser
   :prog: artiq_run
   :nodefault:

.. _frontend-artiq-master:

:mod:`artiq.frontend.artiq_master`
----------------------------------

.. automodule:: artiq.frontend.artiq_master
.. argparse::
   :ref: artiq.frontend.artiq_master.get_argparser
   :prog: artiq_master
   :nodefault:

.. _frontend-artiq-client:

:mod:`artiq.frontend.artiq_client`
----------------------------------
.. automodule:: artiq.frontend.artiq_client
.. argparse::
   :ref: artiq.frontend.artiq_client.get_argparser
   :prog: artiq_client
   :nodefault:

.. _frontend-artiq-dashboard:

:mod:`artiq.frontend.artiq_dashboard`
-------------------------------------

.. automodule:: artiq.frontend.artiq_dashboard
.. argparse::
   :ref: artiq.frontend.artiq_dashboard.get_argparser
   :prog: artiq_dashboard
   :nodefault:

.. _frontend-artiq-browser:

:mod:`artiq.frontend.artiq_browser`
-----------------------------------

.. automodule:: artiq.frontend.artiq_browser
.. argparse::
   :ref: artiq.frontend.artiq_browser.get_argparser
   :prog: artiq_browser
   :nodefault:

:mod:`artiq.frontend.artiq_session`
-----------------------------------

.. automodule:: artiq.frontend.artiq_session

ARTIQ session manager. Automatically runs the master, dashboard and local controller manager on the current machine. The latter requires the ``artiq-comtools`` package to be installed. Requires access to device database, for the sake of the master.

When supplying arguments to individual front-end tools, use ``=`` to avoid ambiguity in argument parsing, e.g.: ::

   artiq_session -m=-g -m=--device-db=alternate_device_db.py -c=-v

and so on.

.. argparse::
   :ref: artiq.frontend.artiq_session.get_argparser
   :prog: artiq_session
   :nodescription:
   :nodefault:

:mod:`artiq_comtools.artiq_ctlmgr`
----------------------------------

.. automodule:: artiq_comtools.artiq_ctlmgr

ARTIQ controller manager. Supplied in the separate package ``artiq-comtools``, which is included with a standard ARTIQ installation but can also be `installed standalone <https://github.com/m-labs/artiq-comtools>`_, with the intention of making it easier to run controllers and controller managers on machines where a full ARTIQ installation may not be necessary or convenient. Requires the master to be running.

.. argparse::
   :ref: artiq_comtools.artiq_ctlmgr.get_argparser
   :prog: artiq_ctlmgr
   :nodescription:
   :nodefault: