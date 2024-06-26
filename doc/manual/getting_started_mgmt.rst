Getting started with the management system
==========================================

In practice, rather than managing experiments by executing ``artiq_run`` over and over, most use cases are better served by using the ARTIQ *management system.* This is the high-level part of ARTIQ, which can be used to schedule experiments, distribute and store the results, and manage devices and parameters. It possesses a detailed GUI and can be used on several machines concurrently, allowing them to coordinate with each other and with the specialized hardware over the network. As a result, multiple users on different machines can schedule experiments or retrieve results on the same ARTIQ system, potentially simultaneously. 

The management system consists of at least two parts:

    a. the **ARTIQ master,** which runs on a single machine, facilitates communication with the core device and peripherals, and is responsible for most of the actual duties of the system, 
    b. one or more **ARTIQ clients,** which may be local or remote and which communicate only with the master. Both a GUI (the **dashboard**) and a straightforward command line client are provided, with many of the same capabilities. 

as well as, optionally, 

    c. one or more **controller managers**, which help coordinate the operation of certain (generally, non-realtime) classes of device. 

In this tutorial, we will explore the basic operation of the management system. Because the various components of the management system run wholly on the host machine, and not on the core device (in other words, they do not inherently involve any kernel functions), it is not necessary to have a core device or any special hardware set up to use it. The examples in this tutorial can all be carried out using only your computer. 

Starting your first experiment with the master
----------------------------------------------

In the previous tutorial, we used the ``artiq_run`` utility to execute our experiments, which is a simple standalone tool that bypasses the management system. We will now see how to run an experiment using the master and the dashboard.  

First, create a folder ``~/artiq-master`` and copy into it the ``device_db.py`` for your system (your device database, exactly as in :ref:`connecting-to-the-core-device`.) The master uses the device database in the same way as ``artiq_run`` when communicating with the core device. Since no devices are actually used in these examples, you can also use the ``device_db.py`` found in ``examples/no_hardware``.

Secondly, create a subfolder ``~/artiq-master/repository`` to contain experiments. By default, the master scans for a folder of this name to determine what experiments are available. If you'd prefer to use a different name, this can be changed by running ``artiq_master -r [folder name]`` instead of ``artiq_master`` below. 

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

This last command should not return, as the master keeps running.

Now, start the dashboard with the following commands in another terminal: ::

    $ cd ~
    $ artiq_dashboard

.. note:: 
    In order to connect to a master over the network, start it with the command ::

        $ artiq_master --bind [hostname or IP]
        
    and then use the option ``--server`` or ``-s`` for clients, as in: :: 
        
        $ artiq_dashboard -s [hostname or IP of the master]
        $ artiq_client -s [hostname or IP of the master]

    Both IPv4 and IPv6 are supported. 

The dashboard should display the list of experiments from the repository folder in a dock called "Explorer". There should be only the experiment we created. Select it and click "Submit", then look at the "Log" dock for the output from this simple experiment.

.. seealso::
    You may note that experiments may be submitted with a due date, a priority level, a pipeline identifier, and other specific settings. Some of these are self-explanatory. Many are scheduling-related. For more information on experiment scheduling, especially when submitting longer experiments or submitting across multiple users, see :ref:`experiment-scheduling`.  

.. _mgmt-arguments:

Adding an argument
------------------

Experiments may have arguments whose values can be set in the dashboard and used in the experiment's code. Modify the experiment as follows: ::

    def build(self):
        self.setattr_argument("count", NumberValue(precision=0, step=1))

    def run(self):
        for i in range(self.count):
            print("Hello World", i)


``NumberValue`` represents a floating point numeric argument. There are many other types, see :class:`~artiq.language.environment` and :class:`~artiq.language.scan`.

Use the command-line client to trigger a repository rescan: ::

    artiq_client scan-repository

The dashboard should now display a spin box that allows you to set the value of the ``count`` argument. Try submitting the experiment as before.

Interactive arguments
---------------------

It is also possible to use interactive arguments, which may be requested and supplied while the experiment is running. This time modify the experiment as follows: ::  

    def build(self):
        pass 
    
    def run(self):
        repeat = True 
        while repeat: 
            print("Hello World")
            with self.interactive(title="Repeat?") as interactive: 
                interactive.setattr_argument("repeat", BooleanValue(True))
            repeat = interactive.repeat 


Trigger a repository rescan and click the button labeled "Recompute all arguments". Now submit the experiment. It should print once, then wait; in the same dock as "Explorer", find and navigate to the tab "Interactive Args". You can now choose and supply a value for the argument mid-experiment. Every time an argument is requested, the experiment pauses until the input is supplied. If you choose to "Cancel" instead, an :exc:`~artiq.language.environment.CancelledArgsError` will be raised (which the experiment can choose to catch, rather than halting.)  

While regular arguments are all requested simultaneously before submitting, interactive arguments can be requested at any point. In order to request multiple interactive arguments at once, place them within the same ``with`` block; see also the example ``interactive.py`` in the ``examples/no_hardware`` folder. 

.. _master-setting-up-git: 
    
Setting up Git integration
--------------------------

So far, we have used the bare filesystem for the experiment repository, without any version control. Using Git to host the experiment repository helps with the tracking of modifications to experiments and with the traceability of a result to a particular version of an experiment.

.. note:: 
    The workflow we will describe in this tutorial corresponds to a situation where the ARTIQ master machine is also used as a Git server where multiple users may push and pull code. The Git setup can be customized according to your needs; the main point to remember is that when scanning or submitting, the ARTIQ master uses the internal Git data (*not* any working directory that may be present) to fetch the latest *fully completed commit* at the repository's head.

We will use the current ``repository`` folder as working directory for making local modifications to the experiments, move it away from the master data directory, and create a new ``repository`` folder that holds the Git data used by the master. Stop the master with Ctrl-C and enter the following commands: ::

    $ cd ~/artiq-master
    $ mv repository ~/artiq-work
    $ mkdir repository
    $ cd repository
    $ git init --bare

Now, push data to into the bare repository. Initialize a regular (non-bare) Git repository into our working directory: ::

    $ cd ~/artiq-work
    $ git init    

Then commit our experiment: ::

    $ git add mgmt_tutorial.py
    $ git commit -m "First version of the tutorial experiment"

and finally, push the commit into the master's bare repository: ::

    $ git remote add origin ~/artiq-master/repository
    $ git push -u origin master

Start the master again with the ``-g`` flag, telling it to treat the contents of the ``repository`` folder (not ``artiq-work``) as a bare Git repository: ::

    $ cd ~/artiq-master
    $ artiq_master -g

.. note:: 
    You need at least one commit in the repository before you can start the master.

There should be no errors displayed, and if you start the GUI again, you will find the experiment there.

To complete the master configuration, we must tell Git to make the master rescan the repository when new data is added to it. Create a file ``~/artiq-master/repository/hooks/post-receive`` with the following contents: ::

   #!/bin/sh
   artiq_client scan-repository --async

Then set the execution permission on it: ::

   $ chmod 755 ~/artiq-master/repository/hooks/post-receive

.. note:: 
    Remote machines may also push and pull into the master's bare repository using e.g. Git over SSH.

Let's now make a modification to the experiment. In the source present in the working directory, add an exclamation mark at the end of "Hello World". Before committing it, check that the experiment can still be executed correctly by running it directly from the filesystem using: ::

    $ artiq_client submit ~/artiq-work/mgmt_tutorial.py

.. note:: 
    You may also use the "Open file outside repository" feature of the GUI, by right-clicking on the explorer.

Verify the log in the GUI. If you are happy with the result, commit the new version and push it into the master's repository: ::

    $ cd ~/artiq-work
    $ git commit -a -m "More enthusiasm"
    $ git push

.. note:: 
    Notice that commands other than ``git push`` are no longer necessary.

The master should now run the new version from its repository.

As an exercise, add another experiment to the repository, commit and push the result, and verify that it appears in the GUI.

.. _getting-started-datasets: 

Datasets
--------

ARTIQ uses the concept of *datasets* to manage the data exchanged with experiments, both supplied *to* experiments (generally, from other experiments) and saved *from* experiments (i.e. results or records). 

Modify the experiment as follows, once again using a single non-interactive argument: ::

    def build(self):
        self.setattr_argument("count", NumberValue(precision=0, step=1))

    def run(self):
        self.set_dataset("parabola", np.full(self.count, np.nan), broadcast=True)
        for i in range(self.count):
            self.mutate_dataset("parabola", i, i*i)
            time.sleep(0.5)

.. tip:: 
    You need to import the ``time`` module, and the ``numpy`` module as ``np``.

Commit, push and submit the experiment as before. Go to the "Datasets" dock of the GUI and observe that a new dataset has been created. Once the experiment has finished executing, navigate to ``~/artiq-master/`` in a terminal or file manager and see that a new directory has been created called ``results``. Your dataset should be stored as an HD5 dump file in ``results`` under ``<date>/<hour>``. 

.. note:: 
    By default, datasets are primarily attributes of the experiments that run them, and are not shared with the master or the dashboard. The ``broadcast=True`` argument specifies that an argument should be shared in real-time with the master, which is responsible for dispatching it to the clients. A more detailed description of dataset methods and their arguments can be found under :mod:`artiq.language.environment.HasEnvironment`. 

Open the file for your first dataset with HDFView, h5dump, or any similar third-party tool, and observe the data we just generated as well as the Git commit ID of the experiment (a hexadecimal hash such as ``947acb1f90ae1b8862efb489a9cc29f7d4e0c645`` which represents a particular state of the Git repository). A list of Git commit IDs can be found by running the ``git log`` command in ``~/artiq-master/``. 

Applets
-------

Often, rather than the HDF dump, we would like to see our result datasets in readable graphical form, preferably immediately. In the ARTIQ dashboard, this is achieved by programs called "applets". Applets are independent programs that add simple GUI features and are run as separate processes (to achieve goals of modularity and resilience against poorly written applets). ARTIQ supplies several applets for basic plotting in the ``artiq.applets`` module, and users may write their own using the provided interfaces. 

.. seealso::
    For developing your own applets, see the references provided on the :ref:`management system page<applet-references>` of this manual. 

For our ``parabola`` dataset, we will create an XY plot using the provided ``artiq.applets.plot_xy``. Applets are configured with simple command line options; we can find the list of available options using the ``-h`` flag. Try running: ::

    $ python3 -m artiq.applets.plot_xy -h 

In our case, we only need to supply our dataset as the y-values to be plotted. Navigate to the "Applet" dock in the dashboard. Right-click in the empty list and select "New applet from template" and "XY". This will generate a version of the applet command that shows all applicable options; edit the command so that it retrieves the ``parabola`` dataset and erase the unused options. The line should now be: :: 

    ${artiq_applet}plot_xy parabola

Run the experiment again, and observe how the points are added one by one to the plot.

RTIO analyzer and the dashboard 
-------------------------------

The :ref:`rtio-analyzer-example` is fully integrated into the dashboard. Navigate to the "Waveform" tab in the dashboard. After running the example experiment in that section, or any other experiment producing an analyzer trace, the waveform results will be directly displayed in this tab. It is also possible to save a trace, reopen it, or export it to VCD directly from the GUI. 

Non-RTIO devices and the controller manager
-------------------------------------------

As described in :ref:`artiq-real-time-i-o-concepts`, there are two classes of equipment a laboratory typically finds itself needing to operate. So far, we have largely discussed ARTIQ in terms of one only: the kind of specialized hardware that requires the very high-resolution timing control ARTIQ provides. The other class comprises the broad range of regular, "slow" laboratory devices, which do *not* require nanosecond precision and can generally be operated perfectly well from a regular PC over a non-realtime channel such as USB. 

To handle these "slow" devices, ARTIQ uses *controllers*, intermediate pieces of software which are responsible for the direct I/O to these devices and offer RPC interfaces to the network. Controllers can be started and run standalone, but are generally handled through the *controller manager*, :mod:`~artiq_comtools.artiq_ctlmgr`, available through the ``artiq-comtools`` package (normally automatically installed together with ARTIQ.) The controller manager in turn communicates with the ARTIQ master, and through it with clients or the GUI. 

To start the controller manager (the master must already be running), the only command necessary is: :: 

    $ artiq_ctlmgr 

Controllers may be run on a different machine from the master, or even on multiple different machines, alleviating cabling issues and OS compatibility problems. In this case, communication with the master happens over the network. If multiple machines are running controllers, they must each run their own controller manager (for which only ``artiq-comtools`` and its few dependencies are necessary, not the full ARTIQ installation.) Use the ``-s`` and ``--bind`` flags of ``artiq_ctlmgr`` to set IP addresses or hostnames to connect and bind to.

Note, however, that the controller for the particular device you are trying to connect to must first exist and be part of a complete Network Device Support Package, or NDSP. :doc:`Some NDSPs are already available <list_of_ndsps>`. If your device is not on this list, the system is designed to make it quite possible to write your own. For this, see the :doc:`developing_a_ndsp` page. 

Once a device is correctly listed in ``device_db.py``, it can be added to an experiment using ``self.setattr_device([device_name])`` and the methods its API offers called straightforwardly as ``self.[device_name].[method_name]``. As long as the requisite controllers are running and available, the experiment can then be executed with ``artiq_run`` or through the management system. 

The ARTIQ session
-----------------

If (as is often the case) you intend to mostly operate your ARTIQ system and its devices from a single machine, i.e., the networked aspects of the management system are largely unnecessary and you will be running master, dashboard, and controller manager on one computer, they can all be started simultaneously with the single command: :: 

    $ artiq_session 

Arguments to the individuals (including ``-s`` and ``--bind``) can still be specified using the ``-m``, ``-d`` and ``-c`` options respectively. 