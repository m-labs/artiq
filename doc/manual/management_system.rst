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

To make more efficient use of resources, experiments are generally split into three phases and pipelined. While one experiment has control of the specialized hardware, others may carry out pre-computation or post-analysis in parallel. There are three stages of a standard experiment users may write code for:

1. The **preparation** stage, which pre-fetches and pre-computes any data that is necessary to run the experiment. Users may implement this stage by overloading the :meth:`~artiq.language.environment.Experiment.prepare` method. It is not permitted to access hardware in this stage.

2. The **run** stage, which corresponds to the body of the experiment. Users *must* implement this stage and overload the :meth:`~artiq.language.environment.Experiment.run` method. In this stage, the experiment has the right to run kernels and access hardware.

3. The **analysis** stage, where raw results collected in the running stage can be post-processed and/or saved. This stage may be implemented by overloading the :meth:`~artiq.language.environment.Experiment.analyze` method. It is not permitted to access hardware in this stage.

.. seealso::
   These steps are implemented in :class:`artiq.language.environment.Experiment`. User-written experiments should usually derive from (sub-class) :class:`artiq.language.environment.EnvExperiment`, which additionally provides access to the methods of :class:`~artiq.language.environment.HasEnvironment`.

Only the :meth:`~artiq.language.environment.Experiment.run` method implementation is mandatory; if the experiment does not fit into the pipelined scheduling model, it can leave one or both of the other methods empty (which is the default). Preparation and analysis stages are forbidden from accessing hardware so as not to interfere with a potential concurrent run stage. Note that they are not *prevented* from doing so, and it is up to the programmer to respect these guidelines.

Consecutive experiments are automatically pipelined by the ARTIQ master's scheduler: first experiment A executes its preparation stage, then experiment A executes its running stage while experiment B executes its preparation stage, and so on.

.. note::
   An experiment A can exit its :meth:`~artiq.language.environment.Experiment.run` method before all its RTIO events have been executed, i.e., while those events are still 'waiting' in the RTIO core buffers. If the next experiment entering the running stage uses :meth:`~artiq.coredevice.core.Core.reset`, those buffers will be cleared, and any remaining events discarded, potentially including those scheduled by A.

   This is a deliberate feature of seamless handover, but can cause problems if the events scheduled by A were important and should not have been skipped. In those cases, it is recommended to ensure the :meth:`~artiq.language.environment.Experiment.run` method of experiment A does not return until *all* its scheduled events have been executed, or that it is followed only by experiments which do not perform a core reset. See also :ref:`RTIO Synchronization<rtio-handover-synchronization>`.

Priorities and timed runs
^^^^^^^^^^^^^^^^^^^^^^^^^

When determining what experiment should begin executing next (i.e. enter its preparation stage), the scheduling looks at the following factors, by decreasing order of precedence:

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

In the run stage, an experiment may yield to the scheduler by calling the :meth:`pause` method of the scheduler. If there are other experiments with higher priority (e.g. a high-priority experiment has been newly submitted, or reached its due date and become eligible for execution), the higher-priority experiments are executed first, and then :meth:`pause` returns. If there are no such experiments, :meth:`pause` returns immediately. To check whether :meth:`pause` would in fact *not* return immediately, use :meth:`~artiq.master.scheduler.Scheduler.check_pause`.

The experiment must place the hardware in a safe state and disconnect from the core device before calling :meth:`pause` - typically by calling ``self.core.comm.close()``, which is equivalent to :meth:`~artiq.coredevice.core.Core.close`, from the host after completion of the kernel.

Accessing the :meth:`pause` and :meth:`~artiq.master.scheduler.Scheduler.check_pause` methods is done through a virtual device called ``scheduler`` that is accessible to all experiments. The scheduler virtual device is requested like any other device, with :meth:`~artiq.language.environment.HasEnvironment.get_device` or :meth:`~artiq.language.environment.HasEnvironment.setattr_device`. See also the detailed reference on the :doc:`mgmt_system_reference` page.

.. note::
   For maximum compatibility, the ``scheduler`` virtual device can also be accessed when running experiments with :mod:`~artiq.frontend.artiq_run`. However, since there is no :mod:`~artiq.master.scheduler.Scheduler` backend, the methods are replaced by simple dummies, e.g. :meth:`~artiq.master.scheduler.Scheduler.check_pause` simply returns false, and requests are printed into the console. Much the same is true of client control broadcasts (see again :doc:`mgmt_system_reference`).

:meth:`~artiq.master.scheduler.Scheduler.check_pause` can be called (via RPC) from a kernel, but :meth:`pause` cannot be.

Internal details
----------------

Internally, the ARTIQ management system uses Simple Python Communications, or `SiPyCo <https://github.com/m-labs/sipyco>`_, which was originally written as part of ARTIQ and later split away as a generic communications library. The SiPyCo manual is hosted `here <https://m-labs.hk/artiq/sipyco-manual/>`_. The core of the management system is largely contained within ``artiq.master``, which contains the :class:`~artiq.master.scheduler.Scheduler`, the various environment and filesystem databases, and the worker processes that execute the experiments themselves.

By default, the master communicates with other processes over four network ports, see :doc:`default_network_ports`, for logging, broadcasts, notifications, and control. All four of these can be customized by using the ``--port`` flags, see :ref:`the front-end reference<frontend-artiq-master>`.

- The logging port is occupied by a :class:`sipyco.logging_tools.Server`, and used only by the worker processes to transmit exceptions and other information to the master.
- The broadcast port is occupied by a :class:`sipyco.broadcast.Broadcaster`, which inherits from :class:`sipyco.pc_rpc.AsyncioServer`. Both the dashboard and the client automatically connect to this port, using :class:`sipyco.broadcast.Receiver` to receive logs and CCB messages.
- The notification port is occupied by a :class:`sipyco.sync_struct.Publisher`. The dashboard and client automatically connect to this port, using :class:`sipyco.sync_struct.Subscriber`. Several objects are given to the :class:`~sipyco.sync_struct.Publisher` to monitor, among them the experiment schedule, the device database, the dataset database, and the experiment list. It notifies the subscribers whenever these objects are modified.
- The control port is occupied by a :class:`sipyco.pc_rpc.Server`, which when running can be queried with :mod:`sipyco.sipyco_rpctool` like any other source of RPC targets. Multiple concurrent calls to target methods are supported. Through this server, the clients are provided with access to control methods to access the various databases and repositories the master handles, through classes like :class:`artiq.master.databases.DeviceDB`, :class:`artiq.master.databases.DatasetDB`, and :class:`artiq.master.experiments.ExperimentDB`.

The experiment database is supported by :class:`artiq.master.experiments.GitBackend` when Git integration is active, and :class:`artiq.master.experiments.FilesystemBackend` if not.

Experiment workers
^^^^^^^^^^^^^^^^^^

The :mod:`~artiq.frontend.artiq_run` tool makes use of many of the same databases and handlers as the master (whereas the scheduler and CCB manager are replaced by dummies, as mentioned above), but also directly runs the build, run, and analyze stages of the experiments. On the other hand, within the management system, the master's :class:`~artiq.master.scheduler.Scheduler` spawns a new worker process for each experiment. This allows for the parallelization of stages and pipelines described above in :ref:`experiment-scheduling`.

The master and the worker processes communicate through IPC, Inter Process Communcation, implemented with :mod:`sipyco.pipe_ipc`. Specifically, it is :mod:`artiq.master.worker_impl` which is spawned as a new process for each experiment, and the class :class:`artiq.master.worker.Worker` which manages the IPC requests of the workers, including access to :class:`~artiq.master.scheduler.Scheduler` but also to devices, datasets, arguments, and CCBs. This allows the worker to support experiment :meth:`~artiq.language.environment.HasEnvironment.build` methods and the :doc:`management system interfaces <mgmt_system_reference>`.

The worker process also executes the experiment code itself. Within the experiment, kernel decorators -- :class:`~artiq.language.core.kernel`, :class:`~artiq.language.core.subkernel`, etc. -- call the ARTIQ compiler as necessary and trigger core device execution.