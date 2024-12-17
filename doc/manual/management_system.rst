Management system
=================

.. note::
   The ARTIQ management system as described here is optional. Experiments can be run one-by-one using :mod:`~artiq.frontend.artiq_run`, and controllers can be run without a controller manager. For their very first steps with ARTIQ or in simple or particular cases, users do not need to deploy the management system. For an introduction to the system and how to use it, see :doc:`getting_started_mgmt`.

Components
----------

See also :doc:`overview` for a visual idea of the management system.

Master
^^^^^^

The :ref:`ARTIQ master <frontend-artiq-master>` is responsible for managing the dataset and device databases, the experiment repository, scheduling and running experiments, archiving results, and distributing real-time results. It is a headless component, and one or several clients (command-line or GUI) use the network to interact with it.

The master expects to be given a directory on startup, the experiment repository, containing these experiments which are automatically tracked and communicated to clients. By default, it simply looks for a directory called ``repository``. The ``-r`` flag can be used to substitute an alternate location. Subdirectories in ``repository`` are also read, and experiments stored in them are known to the master. They will be displayed as folders in the dashboard's explorer.

It also expects access to a ``device_db.py``, with a corresponding flag ``--device-db`` to substitute a different file name. Additionally, it will reference or create certain files in the directory it is run in, among them ``dataset_db.mdb``, the LMDB database containing persistent datasets, ``last_rid.pyon``, which simply holds the last used RID, and the ``results`` directory. For more on the device and dataset databases, see also :doc:`environment`.

.. note::
   Because the other parts of the management system often display knowledge of the information stored in these files, confusion can sometimes result about where it is really stored and how it is distributed. Device databases, datasets, results, and experiments are all solely kept and administered by the master, which communicates with dashboards, clients, and controller managers over the network whenever necessary.

   Notably, clients and dashboards normally do not *send in* experiments to the master. Rather, they make requests from the list of experiments the master already knows about, primarily those in ``repository``, but also in the master's local file system. This is true even if ``repository`` is configured as a Git repository and cloned onto other machines.

   The only exception is the command line client's ``--content`` flag, which allows submission by content, i.e. sending in experiment files which may be otherwise unknown to the master. This feature however has some important limitations; see below in :ref:`submission-details`.

The ARTIQ master should not be confused with the 'master' device in a DRTIO system, which is only a designation for the particular core device acting as central node in a distributed configuration of ARTIQ. The two concepts are otherwise unrelated.

Clients
^^^^^^^

The :ref:`command-line client <frontend-artiq-client>` connects to the master and permits modification and monitoring of the databases, reading the experiment schedule and log, and submitting experiments.

The :ref:`dashboard <frontend-artiq-dashboard>` connects to the master and is the main method of interacting with it. The main roles of the dashboard are scheduling of experiments, setting of their arguments, examining the schedule, displaying real-time results, and debugging TTL and DDS channels in real time.

The dashboard remembers and restores GUI state (window/dock positions, last values entered by the user, etc.) in between instances. This information is stored in a file called ``artiq_dashboard_{server}_{port}.pyon`` in the configuration directory (e.g. generally ``~/.config/artiq`` for Unix, same as data directory for Windows), distinguished in subfolders by ARTIQ version.

.. note::

   To find where the configuration files are stored on your machine, try the command: ::

      python -c "from artiq.tools import get_user_config_dir; print(get_user_config_dir())"

Browser
^^^^^^^

The :ref:`browser <frontend-artiq-browser>` is used to read ARTIQ ``results`` HDF5 files and run experiment :meth:`~artiq.language.environment.Experiment.analyze` functions, in particular to retrieve previous result databases, process them, and display them in ARTIQ applets. The browser also remembers and restores its GUI state; this is stored in a file called simply ``artiq_browser.pyon``, kept in the same configuration directory as the dashboard.

The browser *can* connect to the master, specifically in order to be able to access the master's store of datasets and to upload new datasets to it, but it does not require such a connection and can also be run completely standalone. However, it requires filesystem access to the ``results`` files to be of much use.

Controller manager
^^^^^^^^^^^^^^^^^^

The controller manager is provided in the ``artiq-comtools`` package (which is also made available separately from mainline ARTIQ, to allow independent use with minimal dependencies) and started with the :mod:`~artiq_comtools.artiq_ctlmgr` command. It is responsible for running and stopping controllers on a machine. One controller manager must be run by each network node that runs controllers.

A controller manager connects to the master and accesses the device database through it to determine what controllers need to be run. The local network address of the connection is used to filter for only those controllers allocated to the current node. Hostname resolution is supported. Changes to the device database are tracked upon rescan and controllers will be stopped and started accordingly.

.. _mgmt-git-integration:

Git integration
---------------

The master may use a Git repository to store experiment source code. Using Git rather than the bare filesystem has many advantages. For example, each HDF5 result file contains the commit ID corresponding to the exact source code it was produced by, making results more reproduceable. See also :ref:`master-setting-up-git`. Generally, it is recommended to use a bare repository (i.e. ``git init --bare``), to easily support push transactions from clients, but both bare and non-bare repositories are supported.

.. tip::
   If you are not familiar with Git, you may find the idea of the master reading experiment files from a bare repository confusing. A bare repository does not normally contain copies of the objects it stores; that is to say, you won't be able to find your experiment files listed in it. What it *does* contain is Git's internal data structures, i.e., ``hooks``, ``objects``, ``config``, and so forth. Among other things, this structure also stores, in compressed form, the full contents of every commit made to the repository. It is this compressed data which the master has access to and can read the experiments from. It is not meant to be directly edited, but it is updated every time new commits are received.

   It may be useful to note that a normal Git repository, created with ``git init``, contains all the same internal data, kept in a hidden directory called ``.git`` to protect it from accidental modifications. Unlike a bare repository, it *also* normally contains working copies of all the files tracked by Git. When working with a non-bare repository, it is important to understand that the master still takes its image of the available experiments from the internal data, and *not* from the working copies. This is why, even in a non-bare repository, changes are only reflected once they are committed. The working copies are simply ignored.

   Other important files -- the device database, the dataset database, the ``results`` directory, and so on -- are normally kept outside of the experiment repository, and in this case, they are not stored or handled by Git at all. The master accesses them through the regular filesystem, not through Git, and other ARTIQ components access them through the master. This can be seen visualized in the :doc:`overview`.

With a bare repository, a Git ``post-receive`` hook can be used to trigger a repository scan every time the repository is pushed to (i.e. updated), as described in the tutorial. This removes the need to trigger repository rescans manually. If you plan to run your ARTIQ system from a single PC, without distributed clients, you may also consider using a non-bare repository and the ``post-commit`` hook instead. In this workflow, changes can be drafted directly in the master's repository, but the master continues to submit from the last completed commit until a new commit is made (and the repository is rescanned).

Behind the scenes, when scanning the repository, the master fetches the last (atomically) completed commit at that time of repository scan and checks it out in a temporary folder. This commit ID is used by default when subsequently submitting experiments. There is one temporary folder by commit ID currently referenced in the system, so concurrently running experiments from different repository revisions is fully supported by the master.

The use of the Git backend is triggered when the master is started with the ``-g`` flag. Otherwise the raw filesystem is read and Git-based features will not be available.

.. _submission-details:

Submission from the raw filesystem
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

By default, the dashboard runs experiments from the repository, that is, the master's temporary checkout folder, whereas the command-line client (``artiq_client submit``) runs experiments from the raw filesystem. This is convenient in order to be able to run working drafts without first committing them.

Be careful with this behavior, however, as it is rather particular. *The raw filesystem* means the immediate local filesystem of the running master. If the client is being run remotely, and you want to submit an experiment from the *client's* local filesystem, e.g. an uncommitted draft in a clone of the experiment repository, use the ``--content`` flag. If you would like to submit an experiment from the repository, in the same way the dashboard does, use the flag ``--repository`` / ``-R``.

To be precise:

- ``artiq_client submit`` should be given a file path that is relative to the location of the master, that is, if the master is run in the directory above its ``repository``, an experiment can be submitted as ``repository/experiment_file.py``. Keep in mind that when working with a bare repository, there may be no copies of experiment files in the raw local filesystem. In this case, files can still be made accessible to the master by network filesystem share or some other method for testing.

- ``artiq_client submit --repository`` should be given a file path relative to the root of the repository, that is, if the experiment is directly within ``repository``, it should be submitted as ``experiment_file.py``. Just as in the dashboard, this file is taken from the last completed commit.

- ``artiq_client submit --content`` should be given a file path that is relative to the location of the client, whether that is local or remote to the master; the contents of the file will be submitted directly to the master to be run. This essentially transfers a raw string, and will not work if the experiment imports or otherwise accesses other files.

Other flags can also be used, such as ``--class-name`` / ``-c`` to select a class name in an experiment which contains several, or ``--revision`` / ``-r`` to use a particular revision. See the reference of :mod:`~artiq.frontend.artiq_client` in :doc:`main_frontend_tools`.

In order to run from the raw filesystem when using the dashboard, right-click in the Explorer window and select the option 'Open file outside repository'. This will open a file explorer window displaying the master's local filesystem, which can be used to select and submit experiments outside of the chosen repository directory. There is no GUI support for submission by content. It is recommended to simply use the command-line client for this purpose.

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

Scheduler attributes
^^^^^^^^^^^^^^^^^^^^

The ``scheduler`` virtual device also exposes information about an experiment's scheduling status through the attributes ``rid``, ``pipeline_name``, ``priority``, and ``expid``. This allows e.g. access to an experiment's current RID as ``self.scheduler.rid``.

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