Management system
=================

.. note::
   The ARTIQ management system as described here is optional. Experiments can be run one-by-one using :mod:`~artiq.frontend.artiq_run`, and controllers can be run without a controller manager. For their very first steps with ARTIQ or in simple or particular cases, users do not need to deploy the management system. For an introduction to the system and how to use it, see :doc:`getting_started_mgmt`.

Components
----------

Master
^^^^^^

The :ref:`ARTIQ master <frontend-artiq-master>` is responsible for managing the dataset and device databases, the experiment repository, scheduling and running experiments, archiving results, and distributing real-time results. It is a headless component, and one or several clients (command-line or GUI) use the network to interact with it.

The master expects to be given a directory on startup, the experiment repository, containing these experiments which are automatically tracked and communicated to clients. By default, it simply looks for a directory called ``repository``. The ``-r`` flag can be used to substitute an alternate location.

It also expects access to a ``device_db.py``, with a corresponding flag ``--device-db`` to substitute a different file name. Additionally, it will reference or create certain files in the directory it is run in, among them ``dataset_db.mdb``, the LMDB database containing persistent datasets, ``last_rid.pyon``, which simply contains the last used RID, and the ``results`` directory.

.. note::
   Because the other parts of the management system all seem to be able to access the information stored in these files, confusion can sometimes result about where it is really stored and how it is distributed. Device databases, datasets, results, and experiments are all solely kept and administered by the master, which communicates information to dashboards, browsers, and clients over the network whenever necessary.

   Notably, clients and dashboards do not send in experiments to the master; they request them from the array of experiments the master knows about, primarily those in ``repository``, but also in the master's local file system, if 'Open file outside repository' is selected. This is true even if ``repository`` is configured as a Git repository and cloned on other machines.

The ARTIQ master should not be confused with the 'master' device in a DRTIO system, which is only a designation for the particular core device acting as central node in a distributed configuration of ARTIQ. The two concepts are otherwise unrelated.

Clients
^^^^^^^

The :ref:`command-line client <frontend-artiq-client>` connects to the master and permits modification and monitoring of the databases, reading the experiment schedule and log, and submitting experiments.

The :ref:`dashboard <frontend-artiq-dashboard>` connects to the master and is the main method of interacting with it. The main roles of the dashboard are scheduling of experiments, setting of their arguments, examining the schedule, displaying real-time results, and debugging TTL and DDS channels in real time.

The dashboard remembers and restores GUI state (window/dock positions, last values entered by the user, etc.) in between instances. This information is stored in a file called ``artiq_dashboard_{server}_{port}.pyon`` in the configuration directory (e.g. generally ``~/.config/artiq`` for Unix, same as data directory for Windows), distinguished in subfolders by ARTIQ version.

Browser
^^^^^^^

The :ref:`browser <frontend-artiq-browser>` is used to read ARTIQ ``results`` HDF5 files and run experiment :meth:`~artiq.language.environment.Experiment.analyze` functions, in particular to retrieve previous result databases, process them, and display them in ARTIQ applets. The browser also remembers and restores its GUI state; this is stored in a file called simply ``artiq_browser``, kept in the same configuration directory as the dashboard.

Controller manager
^^^^^^^^^^^^^^^^^^

The controller manager is provided in the ``artiq-comtools`` package (which is also made available separately from mainline ARTIQ, to allow independent use with minimal dependencies) and started with the :mod:`~artiq_comtools.artiq_ctlmgr` command. It is responsible for running and stopping controllers on a machine. One controller manager must be run by each network node that runs controllers.

A controller manager connects to the master and accesses the device database through it to determine what controllers need to be run. The local network address of the connection is used to filter for only those controllers allocated to the current node. Hostname resolution is supported. Changes to the device database are tracked and controllers will be stopped and started accordingly.

.. _mgmt-git-integration:

Git integration
---------------

The master may use a Git repository to store experiment source code. Using Git has many advantages. For example, each result file (HDF5) contains the commit ID corresponding to the exact source code it was produced by, which helps reproducibility. Although the master also supports non-bare repositories, it is recommended to use a bare repository (e.g. ``git init --bare``) to easily support push transactions from clients.

You will want Git to notify the master every time the repository is pushed to (e.g. updated), so that the master knows to rescan the repository for new or changed experiments. This is easiest done with the ``post-receive`` hook, as described in :ref:`master-setting-up-git`.

.. note::
   If you plan to run the ARTIQ system entirely on a single machine, you may also consider using a non-bare repository and the ``post-commit`` hook to trigger repository scans every time you commit changes (locally). In this case, note that the ARTIQ master never uses the repository's working directory, but only what is committed. More precisely, when scanning the repository, it fetches the last (atomically) completed commit at that time of repository scan and checks it out in a temporary folder. This commit ID is used by default when subsequently submitting experiments. There is one temporary folder by commit ID currently referenced in the system, so concurrently running experiments from different repository revisions is fully supported by the master.

By default, the dashboard runs experiments from the repository, whereas the command-line client (``artiq_client submit``) runs experiments from the raw filesystem (which is useful for iterating rapidly without creating many disorganized commits). In order to run from the raw filesystem when using the dashboard, right-click in the Explorer window and select the option 'Open file outside repository'. In order to run from the repository when using the command-line client, simply pass the ``-R`` flag.

.. _experiment-scheduling:

Experiment scheduling
---------------------

Basics
^^^^^^

To make more efficient use of hardware resources, experiments are generally split into three phases and pipelined, such that potentially compute-intensive pre-computation or analysis phases may be executed in parallel with the bodies of other experiments, which access hardware.

.. seealso::
   These steps are implemented in :class:`~artiq.language.environment.Experiment`. However, user-written experiments should usually derive from (sub-class) :class:`artiq.language.environment.EnvExperiment`, which additionally provides access to the methods of :class:`artiq.language.environment.HasEnvironment`.

There are three stages of a standard experiment users may write code in:

1. The **preparation** stage, which pre-fetches and pre-computes any data that necessary to run the experiment. Users may implement this stage by overloading the :meth:`~artiq.language.environment.Experiment.prepare` method. It is not permitted to access hardware in this stage, as doing so may conflict with other experiments using the same devices.
2. The **run** stage, which corresponds to the body of the experiment and generally accesses hardware. Users must implement this stage and overload the :meth:`~artiq.language.environment.Experiment.run` method.
3. The **analysis** stage, where raw results collected in the running stage are post-processed and may lead to updates of the parameter database. This stage may be implemented by overloading the :meth:`~artiq.language.environment.Experiment.analyze` method.

Only the :meth:`~artiq.language.environment.Experiment.run` method implementation is mandatory; if the experiment does not fit into the pipelined scheduling model, it can leave one or both of the other methods empty (which is the default).

Consecutive experiments are then executed in a pipelined manner by the ARTIQ master's scheduler: first experiment A runs its preparation stage, than experiment A executes its running stage while experiment B executes its preparation stage, and so on.

.. note::
    The next experiment (B) may start its :meth:`~artiq.language.environment.Experiment.run` before all events placed into (core device) RTIO buffers by the previous experiment (A) have been executed. These events may then execute while experiment B's :meth:`~artiq.language.environment.Experiment.run` is already in progress. Using :meth:`~artiq.coredevice.core.Core.reset` in experiment B will clear the RTIO buffers, discarding pending events, including those left over from A.

    Interactions between events of different experiments can be avoided by preventing the :meth:`~artiq.language.environment.Experiment.run` method of experiment A from returning until all events have been executed. This is discussed in the section on RTIO :ref:`rtio-handover-synchronization`.

Priorities and timed runs
^^^^^^^^^^^^^^^^^^^^^^^^^

When determining what experiment should begin executing next (i.e. enter the preparation stage), the scheduling looks at the following factors, by decreasing order of precedence:

1. Experiments may be scheduled with a due date. This is considered the *earliest possible* time of their execution (rather than a deadline, or latest possible -- ARTIQ makes no guarantees about experiments being started or completed before any specified time). If a due date is set and it has not yet been reached, the experiment is not eligible for preparation.
2. The integer priority value specified by the user.
3. The due date itself. The earliest (reached) due date will be scheduled first.
4. The run identifier (RID), an integer that is incremented at each experiment submission. This ensures that, all else being equal, experiments are scheduled in the same order as they are submitted.

Multiple pipelines
^^^^^^^^^^^^^^^^^^

Experiments must be placed into a pipeline at submission time, set by the "Pipeline" field. The master supports multiple simultaneous pipelines, which will operate in parallel. Pipelines are identified by their names, and are automatically created (when an experiment is scheduled with a pipeline name that does not yet exist) and destroyed (when they run empty). By default, all experiments are submitted into the same pipeline, ``main``.

When using multiple pipelines it is the responsibility of the user to ensure that experiments scheduled in parallel will never conflict with those of another pipeline over resources (e.g. attempt to use the same devices simultaneously).

Pauses
^^^^^^

In the run stage, an experiment may yield to the scheduler by calling the :meth:`pause` method of the scheduler.
If there are other experiments with higher priority (e.g. a high-priority experiment has been newly submitted, or reached its due date and become eligible for execution), the higher-priority experiments are executed first, and then :meth:`pause` returns. If there are no such experiments, :meth:`pause` returns immediately. To check whether :meth:`pause` would in fact *not* return immediately, use :meth:`artiq.master.scheduler.Scheduler.check_pause`.

The experiment must place the hardware in a safe state and disconnect from the core device (typically, by calling ``self.core.comm.close()`` from the kernel, which is equivalent to :meth:`artiq.coredevice.core.Core.close`) before calling :meth:`pause`.

Accessing the :meth:`pause` and :meth:`~artiq.master.scheduler.Scheduler.check_pause` methods is done through a virtual device called ``scheduler`` that is accessible to all experiments. The scheduler virtual device is requested like regular devices using :meth:`~artiq.language.environment.HasEnvironment.get_device` (``self.get_device()``) or :meth:`~artiq.language.environment.HasEnvironment.setattr_device` (``self.setattr_device()``).

:meth:`~artiq.master.scheduler.Scheduler.check_pause` can be called (via RPC) from a kernel, but :meth:`pause` must not be.