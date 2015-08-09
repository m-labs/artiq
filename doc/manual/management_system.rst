Management system
=================

The management system described below is optional: experiments can be run one by one using ``artiq_run``, and the controllers can run stand-alone (without a controller manager). For their very first steps with ARTIQ or in simple or particular cases, users do not need to deploy the management system.

Components
**********

Master
------

The master is responsible for managing the parameter and device databases, the experiment repository, scheduling and running experiments, archiving results, and distributing real-time results.

The master is a headless component, and one or several clients (command-line or GUI) use the network to interact with it.

Controller manager
------------------

Controller managers are responsible for running and stopping controllers on a machine. There is one controller manager per network node that runs controllers.

A controller manager connects to the master and uses the device database to determine what controllers need to be run. Changes in the device database are tracked by the manager and controllers are started and stopped accordingly.

Controller managers use the local network address of the connection to the master to filter the device database and run only those controllers that are allocated to the current node. Hostname resolution is supported.

Command-line client
-------------------

The command-line client connects to the master and permits modification and monitoring of the databases, monitoring the experiment schedule and log, and submitting experiments.

GUI client
----------

The GUI client connects to the master and is the main way of interacting with it. The main features of the GUI are scheduling of experiments, setting of their arguments, examining the schedule, displaying real-time results, and debugging TTL and DDS channels in real time.

Experiment scheduling
*********************

Git integration
***************

The master may use a Git repository for the storage of experiment source code. Using Git has many advantages. For example, each result file (HDF5) contains the commit ID corresponding to the exact source code that produced it, which helps reproducibility.

Even though the master also supports non-bare repositories, it is recommended to use a bare repository so that it can easily support push transactions from clients. Create it with e.g.: ::

   mkdir experiments
   cd experiments
   git init --bare

You want Git to notify the master every time the repository is pushed to (updated), so that it is rescanned for experiments and e.g. the GUI controls and the experiment list are updated.

Create a file named ``post-receive`` in the ``hooks`` folder (this folder has been created by the ``git`` command), containing the following: ::

   #!/bin/sh
   artiq_client scan-repository

Then set the execution permission on it: ::

   chmod 755 hooks/post-receive

You may now run the master with the Git support enabled: ::

   artiq_master -g -r /path_to/experiments

Push commits containing experiments to the bare repository using e.g. Git over SSH, and the new experiments should automatically appear in the GUI.

.. note:: If you plan to run the ARTIQ system entirely on a single machine, you may also consider using a non-bare repository and the ``post-commit`` hook to trigger repository scans every time you commit changes (locally). The ARTIQ master never uses the repository's working directory, but only what is committed.

The GUI always runs experiments from the repository. The command-line client, by default, runs experiment from the raw filesystem (which is useful for iterating rapidly without creating many disorganized commits). If you want to use the repository instead, simply pass the ``-R`` option.

Reference
*********

.. argparse::
   :ref: artiq.frontend.artiq_master.get_argparser
   :prog: artiq_master

.. argparse::
   :ref: artiq.frontend.artiq_ctlmgr.get_argparser
   :prog: artiq_ctlmgr

.. argparse::
   :ref: artiq.frontend.artiq_client.get_argparser
   :prog: artiq_client

.. argparse::
   :ref: artiq.frontend.artiq_gui.get_argparser
   :prog: artiq_gui
