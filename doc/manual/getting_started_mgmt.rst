Getting started with the management system
==========================================

In practice, rather than managing experiments by executing ``artiq_run`` over and over, most use cases are better served by using the ARTIQ *management system.* This is the high-level part of ARTIQ, which can be used to schedule experiments, distribute and store the results, and manage devices and parameters. It possesses a detailed GUI, the ARTIQ dashboard, and can be used on several machines concurrently, communicating with each other and the ARTIQ core device over the network. Accordingly, multiple users on different machines can schedule experiments or retrieve results on the same ARTIQ system, potentially at the same time. 

In practice, the management system consists of at least two parts: the ARTIQ master, which runs on a single machine, communicates directly with the core device, and is responsible for most of the actual duties of the system, and one or more ARTIQ clients, which may be local or remote and which communicate only with the master. As well as the dashboard GUI, a straightforward command line client is also provided.

In this tutorial, we will explore the basic operation of the management system. Because the management system only interfaces with the core device, rather than running on it, it is not actually necessary to have a core device set up or connected to follow these steps. Most of the examples in this tutorial can be carried out using only your computer. 

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
    The ``artiq_dashboard`` program will generate and use a file called ``artiq_dashboard.pyon`` in the current directory to save and restore the GUI state (window/dock positions, last values entered by the user, etc.).

.. note:: 
    In order to connect to a master over the network, start it with the command ::

        $ artiq_master --bind [hostname or IP]
        
    and then use the option ``--server`` or ``-s`` for clients, as in: :: 
        
        $ artiq_dashboard -s [hostname or IP of the master]
        $ artiq_client -s [hostname or IP of the master]

    Both IPv4 and IPv6 are supported. 

The dashboard should display the list of experiments from the repository folder in a dock called "Explorer". There should be only the experiment we created. Select it and click "Submit", then look at the "Log" dock for the output from this simple experiment.

Adding an argument
------------------

Experiments may have arguments whose values can be set in the dashboard and used in the experiment's code. Modify the experiment as follows: ::

    def build(self):
        self.setattr_argument("count", NumberValue(precision=0, step=1))

    def run(self):
        for i in range(self.count):
            print("Hello World", i)


``NumberValue`` represents a floating point numeric argument. There are many other types, see :class:`artiq.language.environment` and :class:`artiq.language.scan`.

Use the command-line client to trigger a repository rescan: ::

    artiq_client scan-repository

The dashboard should now display a spin box that allows you to set the value of the ``count`` argument. Try submitting the experiment as before.

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

.. note:: 
    Submitting an experiment from the repository using the ``artiq_client`` command-line tool is done using the ``-R`` flag.

Verify the log in the GUI. If you are happy with the result, commit the new version and push it into the master's repository: ::

    $ cd ~/artiq-work
    $ git commit -a -m "More enthusiasm"
    $ git push

.. note:: 
    Notice that commands other than ``git push`` are no longer necessary.

The master should now run the new version from its repository.

As an exercise, add another experiment to the repository, commit and push the result, and verify that it appears in the GUI.

Datasets
--------

Modify the experiment as follows, once again using a single non-interactive argument: ::

    def build(self):
        self.setattr_argument("count", NumberValue(precision=0, step=1))

    def run(self):
        self.set_dataset("parabola", np.full(self.count, np.nan), broadcast=True)
        for i in range(self.count):
            self.mutate_dataset("parabola", i, i*i)
            time.sleep(0.5)

.. note:: 
    You need to import the ``time`` module, and the ``numpy`` module as ``np``.

Commit, push and submit the experiment as before. Go to the "Datasets" dock of the GUI and observe that a new dataset has been created. We will now create a new XY plot showing this new result.

Plotting in the ARTIQ dashboard is achieved by programs called "applets". Applets are independent programs that add simple GUI features and are run as separate processes (to achieve goals of modularity and resilience against poorly written applets). Users may write their own applets, or use those supplied with ARTIQ (in the ``artiq.applets`` module) that cover basic plotting.

Applets are configured through their command line to select parameters such as the names of the datasets to plot. The list of command-line options can be retrieved using the ``-h`` option; for an example you can run ``python3 -m artiq.applets.plot_xy -h`` in a terminal.

In our case, create a new applet from the XY template by right-clicking in the empty applet list, and edit the "Command" field so that it retrieves the ``parabola`` dataset (the line should be ``${artiq_applet}plot_xy parabola``). Run the experiment again, and observe how the points are added one by one to the plot.

After the experiment has finished executing, the results are written to a HDF5 file that resides in ``~/artiq-master/results/<date>/<hour>``. Open that file with HDFView or h5dump, and observe the data we just generated as well as the Git commit ID of the experiment (a hexadecimal hash such as ``947acb1f90ae1b8862efb489a9cc29f7d4e0c645`` that represents the data at a particular time in the Git repository). The list of Git commit IDs can be found using the ``git log`` command in ``~/artiq-work``.

.. note:: 
    HDFView and h5dump are third-party tools not supplied with ARTIQ.