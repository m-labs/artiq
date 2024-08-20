Data and user interfaces
========================

Beyond running single experiments, or basic use of master, client, and dashboard, ARTIQ supports a much broader range of interactions between its different components. These integrations allow for system control which is extensive, flexible, and dynamic, with space for different workflows and methodologies depending on the needs of particular sets of experiments. We will now explore some of these further tools and systems.

.. note::

    This page follows up directly on :doc:`getting_started_mgmt`, but discusses a broader range of features, most of which continue to rest on the foundation of the management system. Some sections (datasets, the browser) are still possible to try out using your PC alone; others (MonInj, the RTIO analyzer) are only meaningful in relation to real-time hardware.

.. _mgmt-datasets:

Datasets and results
--------------------

ARTIQ uses the concept of *datasets* to manage the data exchanged with experiments, both supplied *to* experiments (generally, from other experiments) and saved *from* experiments (i.e. results or records). We will now see how to view and manipulate datasets, both in experiments or through the management system. Create a new experiment as follows: ::

    from artiq.experiment import *
    import numpy as np
    import time

    class Datasets(EnvExperiment):
        """Dataset tutorial"""
        def build(self):
            pass  # no devices used

        def run(self):
            self.set_dataset("parabola", np.full(10, np.nan), broadcast=True)
            for i in range(10):
                self.mutate_dataset("parabola", i, i*i)
                time.sleep(0.5)

Save it as ``dataset_tutorial.py``. Commit and push your changes, or rescan the repository, whichever is appropriate for your management system configuration. Submit the experiment. In the same window as 'Explorer', navigate to the 'Dataset' tab and observe that a new dataset has been created under the name ``parabola``. As the experiment runs, the values are progressively calculated and entered.

.. note::
    By default, datasets are primarily attributes of the experiments that run them, and are not shared with the master or the dashboard. The ``broadcast=True`` argument specifies that a dataset should be shared in real-time with the master, which is then responsible for storing it in the dataset database ``dataset_db.mdb`` and dispatching it to any clients. For more about dataset options see the :ref:`Environment <environment-datasets>` page.

As long as ``archive=False`` is not explicitly set, datasets are among the information preserved by the master in the ``results`` folder. The files in ``results`` are organized in subdirectories based on the time they were executed, as ``results/<date>/<hour>/``; their individual filenames are a combination of the RID assigned to the execution and the name of the experiment module itself. As such, results are stored in a unique and identifiable location for each iteration of an experiment, even if a dataset is overwritten in the master.

You can open the result file for this experiment with HDFView, h5dump, or any similar third-party tool. Observe that it contains the dataset we just generated, as well as other useful information such as RID, run time, start time, and the Git commit ID of the repository at the time of the experiment (a hexadecimal hash such as ``947acb1f90ae1b8862efb489a9cc29f7d4e0c645``).

.. tip::
    If you are not familiar with Git, try running ``git log`` in either of your connected Git repositories to see a history of commits in the repository which includes their respective hashes. As long as this history remains intact, you can use a hash of this kind of to uniquely identify, and even retrieve, the state of the files in the repository at the time this experiment was run. In oher words, when running experiments from a Git repository, it's always possible to retrieve the code that led to a particular set of results.

Applets
^^^^^^^

Most of the time, rather than the HDF dump, we would like to see our result datasets in a readable graphical form, preferably without opening any third-party applications. In the ARTIQ dashboard, this is achieved by programs called "applets". Applets provide simple, modular GUI features; are run independently from the dashboard as separate processes to achieve goals of modularity and resilience. ARTIQ supplies several applets for basic plotting in the :mod:`artiq.applets` module, and provides interfaces so users can write their owns.

.. seealso::
    For more about developing your own applets, see the references provided on the :ref:`Management system reference<applet-references>` page of this manual.

For our ``parabola`` dataset, we will create an XY plot using the provided :mod:`artiq.applets.plot_xy`. Applets are configured with simple command line options. To figure out what configurations are accepted, use the ``-h`` flag, as in: ::

    $ python3 -m artiq.applets.plot_xy -h

In our case, we only need to supply our dataset to the applet to be plotted. Navigate to the "Applet" dock in the dashboard. Right-click in the empty list and select "New applet from template" and "XY". This will generate a version of the applet command which shows all the configuration options; edit the line so that it retrieves the ``parabola`` dataset and erase the unused options. It should look like: ::

    ${artiq_applet}plot_xy parabola

Run the experiment again, and observe how the points are added as they are generated to the plot in the applet window.

.. tip::
    Datasets and applets can both be arranged in groups for organizational purposes. (In fact, so can arguments; see the reference of :meth:`~artiq.language.environment.HasEnvironment.setattr_argument`). For datasets, use a dot (``.``) in names to separate folders. For applets, left-click in the applet list to see the option 'Create Group'. You can drag and drop to move applets in and out of groups, or select a particular group with a click to create new applets in that group. Deselect applets or groups with CTRL+click.

The ARTIQ browser
^^^^^^^^^^^^^^^^^

ARTIQ also possesses a second GUI, specifically targeted for the manipulation and analysis of datasets, called the ARTIQ browser. It is independent, and does not require either a running master or a core device to operate; a connection to the master is only necessary if you want to upload edited datasets back to the main management system. Open ``results`` in the browser by running: ::

    $ cd ~/artiq-master
    $ artiq_browser ./results

Navigate to the entry containing your ``parabola`` datasets in the file explorers on the left. To bring the dataset into the browser, click on the HDF5 file.

To open an experiment, click on 'Experiment' at the top left. Observe that instead of 'Submit', the option given is 'Analyze'. Where :mod:`~artiq.frontend.artiq_run` and :mod:`~artiq.frontend.artiq_master` ultimately call :meth:`~artiq.language.environment.Experiment.prepare`, :meth:`~artiq.language.environment.Experiment.run`, and :meth:`~artiq.language.environment.Experiment.analyze`, the browser limits itself to :meth:`~artiq.language.environment.Experiment.analyze`. Nonetheless, it still accepts arguments.

As described later in :ref:`experiment-scheduling`, only :meth:`~artiq.language.environment.Experiment.run` is obligatory for experiments to implement, and only :meth:`~artiq.language.environment.Experiment.run` is permitted to access hardware; the preparation and analysis stages occur before and after, and are limited to the host machine. The browser allows for re-running the post-experiment :meth:`~artiq.language.environment.Experiment.analyze`, potentially with different arguments or an edited algorithm, while accessing the datasets from opened ``results`` files.

Notably, the browser does not merely act as an HD5 viewer, but also allows the use of ARTIQ applets to plot and view the data. For this, see the lower left dock; applets can be opened, closed, and managed just as they are in the dashboard, once again accessing datasets from ``results``.

.. _mgmt-ctlmgr:

Non-RTIO devices and the controller manager
-------------------------------------------

As described in :doc:`rtio`, there are two classes of equipment a laboratory typically finds itself needing to operate. So far, we have largely discussed ARTIQ in terms of one only: specialized hardware which requires the very high-resolution timing control ARTIQ provides. The other class comprises the broad range of regular, "slow" laboratory devices, which do *not* require nanosecond precision and can generally be operated perfectly well from a regular PC over a non-realtime channel such as USB.

To handle these "slow" devices, ARTIQ uses *controllers*, intermediate pieces of software which are responsible for the direct I/O to these devices and offer RPC interfaces to the network. By convention, ARTIQ controllers are named with the prefix ``aqctl_``. Controllers can be started and run standalone, but are generally handled through the *controller manager*, :mod:`~artiq_comtools.artiq_ctlmgr`. The controller manager in turn communicates with the ARTIQ master, and through it with clients or the GUI.

Like clients, controllers do not need to be run on the same machine as the master. Various controllers in a device database may in fact be distributed across multiple machines, in whatever way is most convenient for the devices in question, alleviating cabling issues and OS compatibility problems. Each machine running controllers must run its own controller manager. Communication with the master happens over the network. Use the ``-s`` flag of :mod:`~artiq_comtools.artiq_ctlmgr` to set the IP address or hostname of a master to bind to.

.. tip::
    The controller manager is made available through the ``artiq-comtools`` package, maintained separately from the main ARTIQ repository. It is considered a dependency of ARTIQ, and is normally included in any ARTIQ installation, but can also be installed independently. This is especially useful when controllers are widely distributed; instead of installing ARTIQ on every machine that runs controllers, only ``artiq-comtools`` and its much lighter set of dependencies are necessary. See the source repository `here <https://github.com/m-labs/artiq-comtools>`_.

We have already used the controller manager in the previous part of the tutorial. To run it, the only command necessary is: ::

    $ artiq_ctlmgr

Note however that in order for the controller manager to be able to start a controller, the controller in question must first exist and be properly installed on the machine the manager is running on. For laboratory devices, this normally means it must be part of a complete Network Device Support Package, or NDSP. :doc:`Some NDSPs are already available <list_of_ndsps>`. If your device is not on this list, the protocol is designed to make it relatively simple to write your own; for more information and a tutorial, see the :doc:`developing_a_ndsp` page.

Once a device is correctly listed in ``device_db.py``, it can be added to an experiment using ``self.setattr_device([device_name])`` and the methods its API offers called straightforwardly as ``self.[device_name].[method_name]``. As long as the requisite controllers are running and available, the experiment can then be executed with :mod:`~artiq.frontend.artiq_run` or through the management system. To understand how to add controllers to the device database, see also :ref:`device-db`.

ARTIQ built-in controllers
^^^^^^^^^^^^^^^^^^^^^^^^^^

Certain built-in controllers are also included in a standard ARTIQ installation, and can be run directly in your ARTIQ shell. They are listed at the end of the :ref:`Utilities <utilities-ctrls>` reference (the commands prefixed with ``aqctl_`` rather than ``artiq_``) and included by default in device databases generated with :mod:`~artiq.frontend.artiq_ddb_template`.

Broadly speaking, these controllers are edge cases, serving as proxies for interactions between clients and the core device, which otherwise do not make direct contact with each other. Features like dashboard MonInj and the RTIO analyzer's Waveform tab, both discussed in more depth below, depend upon a respective proxy controller to function. A proxy controller is also used to communicate the core log to dashboards.

Although they are listed in the references for completeness' sake, there is normally no reason to run the built-in controllers independently. A controller manager run alongside the master (or anywhere else, provided the given addresses are edited accordingly; proxy controllers communicate with the core device by network just as the master does) is more than sufficient.

.. _interactivity-moninj:

Using MonInj
------------

One of ARTIQ's most convenient features is the Monitor/Injector, commonly known as MonInj. This feature allows for checking (monitoring) the state of various peripherals and setting (injecting) values for their parameters, directly and without any need to explicitly run an experiment for either. MonInj is integrated into ARTIQ on a gateware level, and (except in the case of injection on certain peripherals) can be used in parallel to running experiments, without interrupting them.

In order to use dashboard MonInj, ``aqctl_moninj_proxy`` or a local controller manager must be running. Given this, navigate to the dashboard's ``MonInj`` tab. Mouse over the second button at the top of the dock, which is labeled 'Add channels'. Clicking on it will open a small pop-up, which allows you to select RTIO channels from those currently available in your system.

.. note::

    Multiple channels can be selected and added simultaneously. The button with a folder icon allows opening independent pop-up MonInj docks, into which channels can also be added. Configurations of docks and channels will be remembered between dashboard restarts.

.. warning::

    Not all ARTIQ/Sinara real-time peripherals support both monitoring *and* injection, and some do not yet support either. Which peripherals belong to which categories has varied somewhat over the history of ARTIQ versions. Depending on the complexity of the peripheral, incorporating monitor or injection support represents a nontrivial engineering effort, which has generally only been undertaken when commissioned by particular research groups or users. The pop-up menu will display only channels that are valid targets for one or the other functionality.

    For DDS/Urukul in particular, injection is supported by a slightly different implementation, which involves automatic submission of a miniature kernel which will override and terminate any other experiments currently executing. Accordingly, Urukul injection should be used carefully.

MonInj can always be tested using the user LEDs, which you can find the folder ``ttl`` in the pop-up menu. Channels are listed according to the types and names given in ``device_db.py``. Add your LED channels to the main dock; their monitored values will be displayed automatically. Try running any experiment that has an effect on LED state to see the monitored values change.

Mouse over one of the LED channel fields to see the two buttons ``OVR``, for override, and ``LVL``, for level. Clicking 'Override' will cause MonInj to take direct control of the channel, overriding any experiments that may be running. Once the channel is overriden, its level can be changed directly from the dashboard, by clicking 'Level' to flip it back and forth.

Command-line monitor
^^^^^^^^^^^^^^^^^^^^

For those peripherals which support monitoring, the command-line :mod:`~artiq.frontend.artiq_rtiomon` utility can be used to see monitor output directly in the terminal. The command-line monitor does not require or interact with the management system or even the device database. Instead, it takes the core device IP address and a channel number as parameters and communicates with the core device directly.

.. tip::
    To remember which channel numbers were assigned to which peripherals, check your device database, specifically the ``channel`` field in local entries.

.. _interactivity-waveform:

Waveform
--------

The RTIO analyzer was briefly presented in :ref:`rtio-analyzer`. Like MonInj, it is directly accessible to the dashboard through its own proxy controller, :mod:`~artiq.frontend.aqctl_coreanalyzer_proxy`. To see it in action with the management system, navigate to the 'Waveform' tab of the dashboard. The dock should display several buttons and a currently empty list of waveforms, distinguishable only by the timeline along the top of the field. Use the 'Add channels' button, similar to that used by MonInj, to add waveforms to the list, for example ``rtio_slack`` and the ``led0`` user LED.

The circular arrow 'Fetch analyzer data' button has the same basic effect as using the command-line :mod:`~artiq.frontend.artiq_coreanalyzer`: it extracts the full contents of the circular analyzer buffer. In order to start from a clean slate, click the fetch button a few times, until the ``analyzer dump is empty aside from stop message`` warning appears. Try running a simple experiment, for example this one, which underflows: ::

    from artiq.experiment import *

    class BlinkToUnderflow(EnvExperiment):
        def build(self):
            self.setattr_device("core")
            self.setattr_device("led0")

        @kernel
        def run(self):
            self.core.reset()
            for i in range(1000):
                self.led0.pulse(.2*us)
                delay(.2*us)

Now fetch the analyzer data again (only once)! Visible waveforms should appear in their respective fields. If nothing is visible to you, the timescale is likely zoomed too far out; adjust by zooming with CTRL+scroll and moving along the timeline by dragging it with your mouse. On a clean slate, ``BlinkToUnderflow`` should represent the first RTIO events on the record, and the waveforms accordingly will be displayed at the very beginning of the timeline.

Eventually, you should be able to see the up-and-down 'square wave' pattern of the blinking LED, coupled with a steadily descending line in the RTIO slack, representing the progressive wearing away of the slack gained using ``self.core.reset()``. This kind of analysis can be especially useful in diagnosing underflows; with some practice, the waveform can be used to ascertain which parts of an experiment are consuming the greatest amounts of slack, thereby causing underflows down the line.

.. tip::

    File options in the top left allow for saving and exporting RTIO traces and channel lists (including to VCD), as well as opening them from saved files.

RTIO logging
^^^^^^^^^^^^

It is possible to dump any Python object so that it appears alongside the waveforms, using the built-in ``rtio_log()`` function, which accepts a log name as its first parameter and an arbitrary number of objects along with it. Try adding it to the ``BlinkToUnderflow`` experiment: ::

    @kernel
    def run(self):
        self.core.reset()
        for i in range(1000):
            self.led0.pulse(.2*us)
            rtio_log("test_trace", "i", i)
            delay(.2*us)

Run this edited experiment. Fetch the analyzer data. Open the 'Add channels' pop-up again; ``test_trace`` should appear as an option now that the experiment has been run. Observe that every ``i`` is printed as a single-point event in a new waveform timeline.

Shortcuts
---------

The last notable tab of the dashboard is called 'Shortcuts'. To demonstrate its use, navigate to the 'Explorer' tab, left-click on an experiment, and select 'Set shortcut'. Binding an experiment to one of the available keys will cause it to be automatically submitted any time the key is pressed. The 'Shortcuts' tab simply displays the current set of bound experiments, and provides controls for opening a submission window or deleting the shortcut.

.. note::
    Experiments submitted by shortcut will always use the argument currently entered into the submission window, if one is open. If no window is currently open, it will simply use the value *last* entered into a submission window. This is true even if that value was never used to submit an experiment.