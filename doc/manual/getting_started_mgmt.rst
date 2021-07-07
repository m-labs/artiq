Getting started with the management system
==========================================

The management system is the high-level part of ARTIQ that schedules the experiments, distributes and stores the results, and manages devices and parameters.

The manipulations described in this tutorial can be carried out using a single computer, without any special hardware.

Starting your first experiment with the master
----------------------------------------------

In the previous tutorial, we used the ``artiq_run`` utility to execute our experiments, which is a simple stand-alone tool that bypasses the ARTIQ management system. We will now see how to run an experiment using the master (the central program in the management system that schedules and executes experiments) and the dashboard (that connects to the master and controls it).

First, create a folder ``~/artiq-master`` and copy the file ``device_db.py`` (containing the device database) found in the ``examples/master`` directory from the ARTIQ sources. The master uses those files in the same way as ``artiq_run``.

Then create a ``~/artiq-master/repository`` sub-folder to contain experiments. The master scans this ``repository`` folder to determine what experiments are available (the name of the folder can be changed using ``-r``).

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

.. note:: The ``artiq_dashboard`` program uses a file called ``artiq_dashboard.pyon`` in the current directory to save and restore the GUI state (window/dock positions, last values entered by the user, etc.).

The dashboard should display the list of experiments from the repository folder in a dock called "Explorer". There should be only the experiment we created. Select it and click "Submit", then look at the "Log" dock for the output from this simple experiment.

.. note:: Multiple clients may be connected at the same time, possibly on different machines, and will be synchronized. See the ``-s`` option of ``artiq_dashboard`` and the ``--bind`` option of ``artiq_master`` to use the network. Both IPv4 and IPv6 are supported.

Adding an argument
------------------

Experiments may have arguments whose values can be set in the dashboard and used in the experiment's code. Modify the experiment as follows: ::


    def build(self):
        self.setattr_argument("count", NumberValue(ndecimals=0, step=1))

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

.. note:: The workflow we will describe in this tutorial corresponds to a situation where the ARTIQ master machine is also used as a Git server where multiple users may push and pull code. The Git setup can be customized according to your needs; the main point to remember is that when scanning or submitting, the ARTIQ master uses the internal Git data (*not* any working directory that may be present) to fetch the latest *fully completed commit* at the repository's head.

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

.. note:: You need at least one commit in the repository before you can start the master.

There should be no errors displayed, and if you start the GUI again, you will find the experiment there.

To complete the master configuration, we must tell Git to make the master rescan the repository when new data is added to it. Create a file ``~/artiq-master/repository/hooks/post-receive`` with the following contents: ::

   #!/bin/sh
   artiq_client scan-repository --async

Then set the execution permission on it: ::

   $ chmod 755 ~/artiq-master/repository/hooks/post-receive

.. note:: Remote machines may also push and pull into the master's bare repository using e.g. Git over SSH.

Let's now make a modification to the experiment. In the source present in the working directory, add an exclamation mark at the end of "Hello World". Before committing it, check that the experiment can still be executed correctly by running it directly from the filesystem using: ::

    $ artiq_client submit ~/artiq-work/mgmt_tutorial.py

.. note:: You may also use the "Open file outside repository" feature of the GUI, by right-clicking on the explorer.

.. note:: Submitting an experiment from the repository using the ``artiq_client`` command-line tool is done using the ``-R`` flag.

Verify the log in the GUI. If you are happy with the result, commit the new version and push it into the master's repository: ::

    $ cd ~/artiq-work
    $ git commit -a -m "More enthusiasm"
    $ git push

.. note:: Notice that commands other than ``git push`` are not needed anymore.

The master should now run the new version from its repository.

As an exercise, add another experiment to the repository, commit and push the result, and verify that it appears in the GUI.

Datasets
--------

Modify the ``run()`` method of the experiment as follows: ::

    def run(self):
        self.set_dataset("parabola", np.full(self.count, np.nan), broadcast=True)
        for i in range(self.count):
            self.mutate_dataset("parabola", i, i*i)
            time.sleep(0.5)

.. note:: You need to import the ``time`` module, and the ``numpy`` module as ``np``.

Commit, push and submit the experiment as before. Go to the "Datasets" dock of the GUI and observe that a new dataset has been created. We will now create a new XY plot showing this new result.

Plotting in the ARTIQ dashboard is achieved by programs called "applets". Applets are independent programs that add simple GUI features and are run as separate processes (to achieve goals of modularity and resilience against poorly written applets). Users may write their own applets, or use those supplied with ARTIQ (in the ``artiq.applets`` module) that cover basic plotting.

Applets are configured through their command line to select parameters such as the names of the datasets to plot. The list of command-line options can be retrieved using the ``-h`` option; for example you can run ``python3 -m artiq.applets.plot_xy -h`` in a terminal.

In our case, create a new applet from the XY template by right-clicking on the applet list, and edit the applet command line so that it retrieves the ``parabola`` dataset (the command line should now be ``${artiq_applet}plot_xy parabola``). Run the experiment again, and observe how the points are added one by one to the plot.

After the experiment has finished executing, the results are written to a HDF5 file that resides in ``~/artiq-master/results/<date>/<hour>``. Open that file with HDFView or h5dump, and observe the data we just generated as well as the Git commit ID of the experiment (a hexadecimal hash such as ``947acb1f90ae1b8862efb489a9cc29f7d4e0c645`` that represents the data at a particular time in the Git repository). The list of Git commit IDs can be found using the ``git log`` command in ``~/artiq-work``.

.. note:: HDFView and h5dump are third-party tools not supplied with ARTIQ.
