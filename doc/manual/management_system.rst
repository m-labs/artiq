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