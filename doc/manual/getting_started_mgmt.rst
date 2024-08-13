Using the management system
===========================

In practice, rather than managing experiments by executing :mod:`~artiq.frontend.artiq_run` over and over, most use cases are better served by using the ARTIQ *management system*. This is the high-level application part of ARTIQ, which can be used to schedule experiments, manage devices and parameters, and distribute and store results. It also allows for distributed use of ARTIQ, with a single master coordinating demands on the system issued over the network by multiple clients. Using this system, multiple users on different machines can schedule experiments or analyze results on the same ARTIQ system, potentially simultaneously, without interfering with each other.

The management system consists of at least two parts:

    a. the **ARTIQ master,** which runs on a single machine, facilitates communication with the core device and peripherals, and is responsible for most of the actual duties of the system,
    b. one or more **ARTIQ clients,** which may be local or remote and which communicate only with the master. Both a GUI (the **dashboard**) and a straightforward **command line client** are provided, with many of the same capabilities.

as well as, optionally,

    c. one or more **controller managers**, which coordinate the operation of certain (generally, non-realtime) classes of device and provide certain services to the clients,
    d. and one or more instances of the **ARTIQ browser**, a GUI application designed to facilitate the analysis of experiment results and datasets.

In this tutorial, we will explore the basic operation of the management system. Because the various components of the management system run wholly on the host machine, and not on the core device (in other words, they do not inherently involve any kernel functions), it is not necessary to have a core device or any specialized hardware set up to use it. The examples in this tutorial can all be carried out using only your host computer.

Running your first experiment with the master
---------------------------------------------

Until now, we have executed experiments using :mod:`~artiq.frontend.artiq_run`, which is a simple standalone tool that bypasses the management system. We will now see how to run an experiment using a master and a client. In this arrangement, the master is responsible for communicating with the core device, scheduling and keeping track of experiments, and carrying out RPCs the core device may call for. Clients submit experiments to the master to be scheduled and, if necessary, query the master about the state of experiments and their results.

First, create a folder called ``~/artiq-master``. Copy into it the ``device_db.py`` for your system (your device database, exactly as in :doc:`getting_started_core`); the master uses the device database in the same way as :mod:`~artiq.frontend.artiq_run` when communicating with the core device.

.. tip::
    Since no devices are actually used in these examples, you can also use a device database in the model of the ``device_db.py`` from ``examples/no_hardware``, which uses resources from ``artiq/sim`` instead of referencing or requiring any real local hardware.

Secondly, create a subfolder ``~/artiq-master/repository`` to contain experiments. By default, the master scans for a folder of this name to determine what experiments are available; if you'd prefer to use a different name, this can be changed by running ``artiq_master -r [folder name]`` instead of ``artiq_master`` below. Experiments don't have to be in the repository to be submitted to the master, but the repository contains those experiments the master is automatically aware of.

Create a very simple experiment in ``~/artiq-master/repository`` and save it as ``mgmt_tutorial.py``: ::

    from artiq.experiment import *

    class MgmtTutorial(EnvExperiment):
        """Management tutorial"""
        def build(self):
            pass  # no devices used

        def run(self):
            print("Hello World")

Start the master with: ::

    $ cd ~/artiq-master
    $ artiq_master

This command should display ``ARTIQ master is now ready`` and not return, as the master keeps running. In another terminal, use the client to request this experiment: ::

    $ artiq_client submit repository/mgmt_tutorial.py

This command should print a message in the format ``RID: 0``, telling you the scheduling ID assigned to the experiment by the master, and exit. Note that it doesn't matter *where* the client is run; the client does not require direct access to ``device_db.py`` or the repository folder, and only directly communicates with the master. Relatedly, the path to an experiment a client submits is given relative to the location of the *master*, not the client.

Return to the terminal where the master is running. You should see an output similar to: ::

    INFO:worker(0,mgmt_tutorial.py):print:Hello World

In other words, a worker created by the master has executed the experiment, and carried out the print instruction. Congratulations!

.. tip::

    In order to run the master and the clients on different PCs, start the master with a ``--bind`` flag: ::

        $ artiq_master --bind [hostname or IP to bind to]

    and then use the option ``--server`` or ``-s`` for clients, as in: ::

        $ artiq_client -s [hostname or IP of the master]
        $ artiq_dashboard -s [hostname or IP of the master]

    Both IPv4 and IPv6 are supported. See also the individual references :mod:`~artiq.frontend.artiq_master`, :mod:`~artiq.frontend.artiq_dashboard`, and :mod:`~artiq.frontend.artiq_client` for more details.

You may also notice that the master has created some other organizational files in its home directory, notably a folder ``results``, where a HDF5 record is preserved of every experiment that is submitted and run. The files in ``results`` will be discussed in greater detail in :doc:`using_data_interfaces`.

Running the dashboard and controller manager
--------------------------------------------

Submitting experiments with :mod:`~artiq.frontend.artiq_client` has some interesting qualities: for instance, experiments can be requested simultaneously by different clients and be relied upon to execute neatly in sequence, which is useful in a distributed context. On the other hand, on an local level, it doesn't necessarily carry many practical advantages over using :mod:`~artiq.frontend.artiq_run`. The real convenience of the management system lies in its GUI, the dashboard. We will now try submitting an experiment using the dashboard.

First, start the controller manager: ::

    $ artiq_ctlmgr

Like the master, this command should not return, as the controller manager keeps running. Note that the controller manager requires access to the device database, but not in the local directory -- it gets that access automatically by connecting to the master.

.. note::
    We will not be using controllers in this part of the tutorial. Nonetheless, the dashboard will expect to be able to contact certain controllers given in the device database, and print error messages if this isn't the case (e.g. ``Is aqctl_moninj_proxy running?``). It is equally possible to check your device database and start the requisite controllers manually, or to temporarily delete their entries from ``device_db.py``, but it's normally quite convenient to let the controller manager handle things. The role and use of controller managers will be covered in more detail in :doc:`using_data_interfaces`.

In a third terminal, start the dashboard: ::

    $ artiq_dashboard

Like :mod:`~artiq.frontend.artiq_client`, the dashboard requires no direct access to the device database or the repository. It communicates with the master to receive information about available experiments and the state of the system.

You should see the list of experiments from the ``repository`` in the dock called 'Explorer'. In our case, this will only be the single experiment we created, listed by the name we gave it in the docstring inside the triple quotes, "Management tutorial". Select it, and in the window that opens, click 'Submit'.

This time you will find the output displayed directly in the dock called 'Log'. The dashboard log combines the master's console output, the dashboard's own logs, and the device logs of the core device itself (if there is one in use); normally, this is the only log it's necessary to check.

Adding a new experiment
-----------------------

Create a new file in your ``repository`` folder, called ``timed_tutorial.py``: ::

    from artiq.experiment import *
    import time

    class TimedTutorial(EnvExperiment):
        """Timed tutorial"""
        def build(self):
            pass  # no devices used

        def run(self):
            print("Hello World")
            time.sleep(10)
            print("Goodnight World")

Save it. You will notice that it does not immediately appear in the 'Explorer' dock. For stability reasons, the master operates with a cached idea of the repository, and changes in the file system will often not be reflected until a *repository rescan* is triggered.

You can ask it to do this through the command-line client: ::

    $ artiq_client scan-repository

or you can right-click in the Explorer and select 'Scan repository HEAD'. Now you should be able to select and submit the new experiment.

If you switch the 'Log' dock to its 'Schedule' tab while the experiment is still running, you will see the experiment appear, displaying its RID, status, priority, and other information. Click 'Submit' again while the first experiment is progress, and a second iteration of the experiment will appear in the Schedule, queued up to execute next in line.

.. note::
    You may have noted that experiments can be submitted with a due date, a priority level, a pipeline identifier, and other specific settings. Some of these are self-explanatory. Many are scheduling-related. For more information on experiment scheduling, see :ref:`experiment-scheduling`.

    In the meantime, you can try out submitting either of the two experiments with different priority levels and take a look at the queues that ensue. If you are interested, you can try submitting experiments through the command line client at the same time, or even open a second dashboard in a different terminal. Observe that no matter the source, all submitted experiments will be accounted for and handled by the scheduler in an orderly way.

.. _mgmt-arguments:

Adding arguments
----------------

Experiments may have arguments, values which can be set in the dashboard on submission and used in the experiment's code. Create a new experiment called ``argument_tutorial.py``, and give it the following :meth:`~artiq.language.environment.HasEnvironment.build` and :meth:`~artiq.language.environment.Experiment.run` functions: ::

    def build(self):
        self.setattr_argument("count", NumberValue(precision=0, step=1))

    def run(self):
    for i in range(self.count):
        print("Hello World", i)

The method :meth:`~artiq.language.environment.HasEnvironment.setattr_argument` acts to set the argument and make its value accessible, similar to the effect of :meth:`~artiq.language.environment.HasEnvironment.setattr_device`. The second input sets the type of the argument; here, :class:`~artiq.language.environment.NumberValue` represents a floating point numerical value. To learn what other types are supported, see :class:`artiq.language.environment` and :class:`artiq.language.scan`.

Rescan the repository as before. Open the new experiment in the dashboard. Above the submission options, you should now see a spin box that allows you to set the value of ``count``. Try setting it and submitting it.

Interactive arguments
---------------------

With standard arguments, it is only possible to use :meth:`~artiq.language.environment.HasEnvironment.setattr_argument` in :meth:`~artiq.language.environment.HasEnvironment.build`; these arguments are always requested at submission time. However, it is also possible to use *interactive* arguments, which can be requested and supplied inside :meth:`~artiq.language.environment.Experiment.run`, while the experiment is being executed. Modify the experiment as follows (and push the result): ::

    def build(self):
        pass

    def run(self):
        repeat = True
        while repeat:
            print("Hello World")
            with self.interactive(title="Repeat?") as interactive:
                interactive.setattr_argument("repeat", BooleanValue(True))
            repeat = interactive.repeat

Close and reopen the submission window, or click on the button labeled 'Recompute all arguments', in order to update the submission parameters. Submit again. It should print once, then wait; you may notice in 'Schedule' that the experiment does not exit, but hangs at status 'running'.

Now, in the same dock as 'Explorer', navigate to the tab 'Interactive Args'. You can now choose and submit a value for 'repeat'. Every time an interactive argument is requested, the experiment pauses until an input is supplied.

.. note::
    If you choose to 'Cancel' instead, an :exc:`~artiq.language.environment.CancelledArgsError` will be raised (which an experiment can catch, instead of halting).

In order to request and supply multiple interactive arguments at once, simply place them in the same ``with`` block; see also the example ``interactive.py`` in ``examples/no_hardware``.


.. _master-setting-up-git:

Setting up Git integration
--------------------------

So far, we have used the bare filesystem for the experiment repository, without any version control. Using Git to host the experiment repository helps with tracking modifications to experiments and with the traceability to a particular version of an experiment.

.. note::
    The workflow we will describe in this tutorial corresponds to a situation where the computer running the ARTIQ master is also used as a Git server to which multiple users may contribute code. The Git setup can be customized according to your needs; the main point to remember is that when scanning or submitting, the ARTIQ master uses the internal Git data (*not* any working directory that may be present) to fetch the latest *fully completed commit* at the repository's head. See the :doc:`management_system` page for notes on alternate workflows.

We will use our current ``repository`` folder as the working directory for making local modifications to the experiments, move it away from the master's data directory, and replace it with a new ``repository`` folder, which will hold only the Git data used by the master. Stop the master with Ctrl+C and enter the following commands: ::

    $ cd ~/artiq-master
    $ mv repository ~/artiq-work
    $ mkdir repository
    $ cd repository
    $ git init bare

Now initialize a regular (non-bare) Git repository in our working directory: ::

    $ cd ~/artiq-work
    $ git init

Then add and commit our experiments: ::

    $ git add mgmt_tutorial.py
    $ git add timed_tutorial.py
    $ git commit -m "First version of the tutorial experiments"

and finally, connect the two repositories and push the commit upstream to the master's repository: ::

    $ git remote add origin ~/artiq-master/repository
    $ git push -u origin master

.. tip::
    If you are not familiar with command-line Git and would like to understand these commands in more detail, search for some tutorials in basic use of Git; there are many available online.

Start the master again with the ``-g`` flag, which tells it to treat its ``repository`` folder as a bare Git repository: ::

    $ cd ~/artiq-master
    $ artiq_master -g

.. note::
    Note that you need at least one commit in the repository before the master can be started.

Now you should be able to restart the dashboard and see your experiments there.

To make things more convenient, we will make Git tell the master to rescan the repository whenever new data is pushed from downstream. Create a file ``~/artiq-master/repository/hooks/post-receive`` with the following contents: ::

   #!/bin/sh
   artiq_client scan-repository --async

Then set its execution permissions: ::

   $ chmod 755 repository/hooks/post-receive

.. note::
    Remote client machines may also push and pull into the master repository, using e.g. Git over SSH.

Let's now make a modification to the experiments. In the working directory ``artiq-work``, open ``mgmt_tutorial.py`` again and add an exclamation mark to the end of "Hello World". Before committing it, check that the experiment can still be executed correctly by submitting it directly from the working directory, using the command-line client: ::

    $ artiq_client submit ~/artiq-work/mgmt_tutorial.py

.. note::
    Alternatively, right-click in the Explorer dock and select the 'Open file outside repository' option for the same effect.

Verify the log in the GUI. If you are happy with the result, commit the new version and push it into the master's repository: ::

    $ cd ~/artiq-work
    $ git commit -a -m "More enthusiasm"
    $ git push

Notice that commands other than ``git commit`` and ``git push`` are no longer necessary. The Git hook should cause a repository rescan automatically, and submitting the experiment in the dashboard should run the new version, with enthusiasm included.

The ARTIQ session
-----------------

Often, you will want to run an instance of the controller manager and dashboard along with the ARTIQ master, whether or not you also intend to allow other clients to connect remotely. For convenience, all three can be started simultaneously with a single command: ::

    $ artiq_session

Arguments to the individual tools (including ``-s`` and ``--bind``) can still be specified using the ``-m``, ``-d`` and ``-c`` options for master, dashboard and manager respectively. Use an equals sign to avoid confusion in parsing, for example: ::

    $ artiq_session -m=-g

to start the session with the master in Git mode. See also :mod:`~artiq.frontend.artiq_session`.