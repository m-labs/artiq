Management system
=================

Master
------

The master is responsible for managing the parameter and device databases, the experiment repository, scheduling and running experiments, archiving results, and distributing real-time results.

The master is a headless component, and one or several clients (command-line or GUI) use the network to interact with it.

.. argparse::
   :ref: artiq.frontend.artiq_master.get_argparser
   :prog: artiq_master

Controller manager
------------------

Controller managers are responsible for running and stopping controllers on a machine. There is one controller manager per network node that runs controllers.

A controller manager connects to the master and uses the device database to determine what controllers need to be run. Changes in the device database are tracked by the manager and controllers are started and stopped accordingly.

Controller managers use the local network address of the connection to the master to filter the device database and run only those controllers that are allocated to the current node. Hostname resolution is supported.

.. argparse::
   :ref: artiq.frontend.artiq_ctlmgr.get_argparser
   :prog: artiq_ctlmgr

Command-line client
-------------------

The command-line client connects to the master and permits modification and monitoring of the databases, monitoring the experiment schedule, and submitting experiments.

.. argparse::
   :ref: artiq.frontend.artiq_client.get_argparser
   :prog: artiq_client

GUI client
----------

The GUI client connects to the master and is the main way of interacting with it.

.. argparse::
   :ref: artiq.frontend.artiq_gui.get_argparser
   :prog: artiq_gui
