Management system
=================

The management system described below is optional: experiments can be run one by one using :mod:`~artiq.frontend.artiq_run`, and the controllers can run stand-alone (without a controller manager). For their very first steps with ARTIQ or in simple or particular cases, users do not need to deploy the management system.

Components
**********

Master
------

The :ref:`master <frontend-artiq-master>` is responsible for managing the parameter and device databases, the experiment repository, scheduling and running experiments, archiving results, and distributing real-time results.

The master is a headless component, and one or several clients (command-line or GUI) use the network to interact with it.

Controller manager
------------------

Controller managers (started using the ``artiq_ctlmgr`` command that is part of the ``artiq-comtools`` package) are responsible for running and stopping controllers on a machine. There is one controller manager per network node that runs controllers.

A controller manager connects to the master and uses the device database to determine what controllers need to be run. Changes in the device database are tracked by the manager and controllers are started and stopped accordingly.

Controller managers use the local network address of the connection to the master to filter the device database and run only those controllers that are allocated to the current node. Hostname resolution is supported.

.. warning:: With some network setups, the current machine's hostname without the domain name resolves to a localhost address (127.0.0.1 or even 127.0.1.1). If you wish to use controllers across a network, make sure that the hostname you provide resolves to an IP address visible on the network (e.g. try providing the full hostname including the domain name).

Command-line client
-------------------

The :ref:`command-line client <frontend-artiq-client>` connects to the master and permits modification and monitoring of the databases, monitoring the experiment schedule and log, and submitting experiments.

Dashboard
---------

The :ref:`dashboard <frontend-artiq-dashboard>` connects to the master and is the main way of interacting with it. The main features of the dashboard are scheduling of experiments, setting of their arguments, examining the schedule, displaying real-time results, and debugging TTL and DDS channels in real time.

Experiment scheduling
*********************

Basics
------

To use hardware resources more efficiently, potentially compute-intensive pre-computation and analysis phases of other experiments are executed in parallel with the body of the current experiment that accesses the hardware.

.. seealso:: These steps are implemented in :class:`~artiq.language.environment.Experiment`. However, user-written experiments should usually derive from (sub-class) :class:`artiq.language.environment.EnvExperiment`.

Experiments are divided into three phases that are programmed by the user:

1. The **preparation** stage, that pre-fetches and pre-computes any data that necessary to run the experiment. Users may implement this stage by overloading the :meth:`~artiq.language.environment.Experiment.prepare` method. It is not permitted to access hardware in this stage, as doing so may conflict with other experiments using the same devices.
2. The **running** stage, that corresponds to the body of the experiment, and typically accesses hardware. Users must implement this stage and overload the :meth:`~artiq.language.environment.Experiment.run` method.
3. The **analysis** stage, where raw results collected in the running stage are post-processed and may lead to updates of the parameter database. This stage may be implemented by overloading the :meth:`~artiq.language.environment.Experiment.analyze` method.

.. note:: Only the :meth:`~artiq.language.environment.Experiment.run` method implementation is mandatory; if the experiment does not fit into the pipelined scheduling model, it can leave one or both of the other methods empty (which is the default).

The three phases of several experiments are then executed in a pipelined manner by the scheduler in the ARTIQ master: experiment A executes its preparation stage, then experiment A executes its running stage while experiment B executes its preparation stage, and so on.

.. note::
    The next experiment (B) may start :meth:`~artiq.language.environment.Experiment.run`\ ing before all events placed into (core device) RTIO buffers by the previous experiment (A) have been executed. These events can then execute while experiment B is :meth:`~artiq.language.environment.Experiment.run`\ ing. Using :meth:`~artiq.coredevice.core.Core.reset` clears the RTIO buffers, discarding pending events, including those left over from A.

    Interactions between events of different experiments can be avoided by preventing the :meth:`~artiq.language.environment.Experiment.run` method of experiment A from returning until all events have been executed. This is discussed in the section on RTIO :ref:`rtio-handover-synchronization`.

Priorities and timed runs
-------------------------

When determining what experiment to begin executing next (i.e. entering the preparation stage), the scheduling looks at the following factors, by decreasing order of precedence:

1. Experiments may be scheduled with a due date. If there is one and it is not reached yet, the experiment is not eligible for preparation.
2. The integer priority value specified by the user.
3. The due date itself. The earlier the due date, the earlier the experiment is scheduled.
4. The run identifier (RID), an integer that is incremented at each experiment submission. This ensures that, all other things being equal, experiments are scheduled in the same order as they are submitted.

Pauses
------

In the run stage, an experiment may yield to the scheduler by calling the ``pause()`` method of the scheduler.
If there are other experiments with higher priority (e.g. a high-priority timed experiment has reached its due date), they are preemptively executed, and then ``pause()`` returns.
Otherwise, ``pause()`` returns immediately.
To check whether ``pause()`` would in fact *not* return immediately, use :meth:`artiq.master.scheduler.Scheduler.check_pause`.

The experiment must place the hardware in a safe state and disconnect from the core device (typically, by calling ``self.core.comm.close()`` from the kernel, which is equivalent to :meth:`artiq.coredevice.core.Core.close`) before calling ``pause()``.

Accessing the ``pause()`` and :meth:`~artiq.master.scheduler.Scheduler.check_pause` methods is done through a virtual device called ``scheduler`` that is accessible to all experiments. The scheduler virtual device is requested like regular devices using :meth:`~artiq.language.environment.HasEnvironment.get_device` (``self.get_device()``) or :meth:`~artiq.language.environment.HasEnvironment.setattr_device` (``self.setattr_device()``).

:meth:`~artiq.master.scheduler.Scheduler.check_pause` can be called (via RPC) from a kernel, but ``pause()`` must not.

Multiple pipelines
------------------

Multiple pipelines can operate in parallel inside the same master. It is the responsibility of the user to ensure that experiments scheduled in one pipeline will never conflict with those of another pipeline over resources (e.g. same devices).

Pipelines are identified by their name, and are automatically created (when an experiment is scheduled with a pipeline name that does not exist) and destroyed (when they run empty).


Git integration
***************

The master may use a Git repository for the storage of experiment source code. Using Git has many advantages. For example, each result file (HDF5) contains the commit ID corresponding to the exact source code that produced it, which helps reproducibility.

Even though the master also supports non-bare repositories, it is recommended to use a bare repository so that it can easily support push transactions from clients. Create it with e.g.: ::

   $ mkdir experiments
   $ cd experiments
   $ git init --bare

You want Git to notify the master every time the repository is pushed to (updated), so that it is rescanned for experiments and e.g. the GUI controls and the experiment list are updated.

Create a file named ``post-receive`` in the ``hooks`` folder (this folder has been created by the ``git`` command), containing the following: ::

   #!/bin/sh
   artiq_client scan-repository

Then set the execution permission on it: ::

   $ chmod 755 hooks/post-receive

You may now run the master with the Git support enabled: ::

   $ artiq_master -g -r /path_to/experiments

Push commits containing experiments to the bare repository using e.g. Git over SSH, and the new experiments should automatically appear in the dashboard.

.. note:: If you plan to run the ARTIQ system entirely on a single machine, you may also consider using a non-bare repository and the ``post-commit`` hook to trigger repository scans every time you commit changes (locally). The ARTIQ master never uses the repository's working directory, but only what is committed. More precisely, when scanning the repository, it fetches the last (atomically) completed commit at that time of repository scan and checks it out in a temporary folder. This commit ID is used by default when subsequently submitting experiments. There is one temporary folder by commit ID currently referenced in the system, so concurrently running experiments from different repository revisions is fully supported by the master.

The dashboard always runs experiments from the repository. The command-line client, by default, runs experiment from the raw filesystem (which is useful for iterating rapidly without creating many disorganized commits). If you want to use the repository instead, simply pass the ``-R`` option.

Scheduler API reference
***********************

The scheduler is exposed to the experiments via a virtual device called ``scheduler``. It can be requested like any regular device, and then the methods below can be called on the returned object.

The scheduler virtual device also contains the attributes ``rid``, ``pipeline_name``, ``priority`` and ``expid`` that contain the corresponding information about the current run.

.. autoclass:: artiq.master.scheduler.Scheduler
   :members:

Client control broadcasts (CCBs)
********************************

Client control broadcasts are requests made by experiments for clients to perform some action. Experiments do so by requesting the ``ccb`` virtual device and calling its ``issue`` method. The first argument of the issue method is the name of the broadcast, and any further positional and keyword arguments are passed to the broadcast.

CCBs are used by experiments to configure applets in the dashboard, for example for plotting purposes.

.. autoclass:: artiq.dashboard.applets_ccb.AppletsCCBDock
   :members:


Front-end tool reference
************************


.. _frontend-artiq-master:

artiq_master
------------

.. argparse::
   :ref: artiq.frontend.artiq_master.get_argparser
   :prog: artiq_master


.. _frontend-artiq-client:

artiq_client
------------

.. argparse::
   :ref: artiq.frontend.artiq_client.get_argparser
   :prog: artiq_client


.. _frontend-artiq-dashboard:

artiq_dashboard
---------------

.. argparse::
   :ref: artiq.frontend.artiq_dashboard.get_argparser
   :prog: artiq_dashboard


artiq_session
-------------

.. argparse::
   :ref: artiq.frontend.artiq_session.get_argparser
   :prog: artiq_session
