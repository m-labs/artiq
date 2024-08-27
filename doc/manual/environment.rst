Environment
===========

ARTIQ experiments exist in an environment, which consists of devices, arguments, and datasets. Access to the environment is handled through the :class:`~artiq.language.environment.HasEnvironment` manager provided by the :class:`~artiq.language.environment.EnvExperiment` class that experiments should derive from.

.. _device-db:

The device database
-------------------

Information about available devices is provided to ARTIQ through a file called the device database, typically called ``device_db.py``, which many of the ARTIQ front-end tools require access to in order to run. The device database specifies:

    * what devices are available to an ARTIQ installation
    * what drivers to use
    * what controllers to use
    * how and where to contact each device, i.e.

      - at which RTIO channel(s) each local device can be reached
      - at which network address each controller can be reached

as well as, if present, how and where to contact the core device itself (e.g., its IP address, often by a field named ``core_addr``).

This is stored in a Python dictionary whose keys are the device names, which the file must define as a global variable with the name ``device_db``. Examples for various system configurations can be found inside the subfolders of ``artiq/examples``. A typical device database entry looks like this: ::

    "led": {
        "type": "local",
        "module": "artiq.coredevice.ttl",
        "class": "TTLOut",
        "arguments": {"channel": 19}
    },

Note that the key (the name of the device) is ``led`` and the value is itself a Python dictionary. Names will later be used to gain access to a device through methods such as ``self.setattr_device("led")``. While in this case ``led`` can be replaced with another name, provided it is used consistently, some names (in particular, ``core``) are used internally by ARTIQ and will cause problems if changed. It is often more convenient to use aliases for renaming purposes, see below.

.. note::
    The device database is generated and stored in the memory of the master when the master is first started. Changes to the ``device_db.py`` file will not immediately affect a running master. In order to update the device database, right-click in the Explorer window and select 'Scan device database', or run the command ``artiq_client scan-devices``.

.. warning::
    It is important to understand that the device database does not *set* your system configuration, only *describe* it. If you change the devices available to your system, it is usually necessary to edit the device database, but editing the database will not change what devices are available to your system.

    Remote (normally, non-realtime) devices must have accessible, suitable controllers and drivers; see :doc:`developing_a_ndsp` for more information, including how to add entries for new remote devices to your device database. Local devices (normally, real-time, e.g. your Sinara hardware) must be connected to your system, and more importantly, your gateware and firmware must have been compiled to account for them, and to expect them at those ports.

    While controllers can be added and removed to your device database on an *ad hoc* basis, in order to make new real-time hardware accessible, it is generally also necessary to recompile and reflash your gateware and firmware. (If you purchase your hardware from M-Labs, you will be provided with new binaries and necessary assistance.) See :doc:`building_developing`.

    Adding or removing new real-time hardware is a difference in *system configuration,* which must be specified at compilation time of gateware and firmware. For Kasli and Kasli-SoC, this is managed in the form of a JSON usually called the :ref:`system description file<system-description>`. The device database generally provides that information to ARTIQ which can change from instance to instance ARTIQ is run, e.g., device names and aliases, network addresses, clock frequencies, and so on. The system configuration defines that information which is *not* permitted to change, e.g., what device is associated with which EEM port or RTIO channels. Insofar as data is duplicated between the two, the device database is obliged to agree with the system description, not the other way around.

If you obtain your hardware from M-Labs, you will always be provided with a ``device_db.py`` to match your system configuration, which you can edit as necessary to add controllers, aliases, and so on. In the relatively unlikely case that you are writing a device database from scratch, the :mod:`~artiq.frontend.artiq_ddb_template` utility can be used to generate a template device database directly from the JSON system description used to compile your gateware and firmware. This is the easiest way to ensure that details such as the allocation of RTIO channel numbers will be represented in the device database correctly. See also the corresponding entry in :ref:`Utilities <ddb-template-tool>`.

Local devices
^^^^^^^^^^^^^

Local device entries are dictionaries which contain a ``type`` field set to ``local``. They correspond to device drivers that are created locally on the master as opposed to using the controller mechanism; this is normally the real-time hardware of the system, including the core, which is itself considered a local device. The ``led`` example above is a local device entry.

The fields ``module`` and ``class`` determine the location of the Python class of the driver. The ``arguments`` field is another (possibly empty) dictionary that contains arguments to pass to the device driver constructor. ``arguments`` is often used to specify the RTIO channel number of a peripheral, which must match the channel number in gateware.

On Kasli and Kasli-SoC, the allocation of RTIO channels to EEM ports is done automatically when the gateware is compiled, and while conceptually simple (channels are assigned one after the other, from zero upwards, for each device entry in the system description file) it is not entirely straightforward (different devices require different numbers of RTIO channels). Again, the easiest way to handle this when writing a new device database is automatically, using :mod:`~artiq.frontend.artiq_ddb_template`.

.. _environment-ctlrs:

Controllers
^^^^^^^^^^^

Controller entries are dictionaries which contain a ``type`` field set to ``controller``. When an experiment requests such a device, a RPC client (see ``sipyco.pc_rpc``) is created and connected to the appropriate controller. Controller entries are also used by controller managers to determine what controllers to run. For an example, see :ref:`the NDSP development page <ndsp-integration>`.

The ``host`` and ``port`` fields configure the TCP connection. The ``target`` field contains the name of the RPC target to use (you may use ``sipyco_rpctool`` on a controller to list its targets). Controller managers run the ``command`` field in a shell to launch the controller, after replacing ``{port}`` and ``{bind}`` by respectively the TCP port the controller should listen to (matching the ``port`` field) and an appropriate bind address for the controller's listening socket.

An optional ``best_effort`` boolean field determines whether to use ``sipyco.pc_rpc.Client`` or ``sipyco.pc_rpc.BestEffortClient``. ``BestEffortClient`` is very similar to ``Client``, but suppresses network errors and automatically retries connections in the background. If no ``best_effort`` field is present, ``Client`` is used by default.

Aliases
^^^^^^^

If an entry is a string, that string is used as a key for another lookup in the device database.

Arguments
---------

Arguments are values that parameterize the behavior of an experiment. ARTIQ supports both interactive arguments, requested and supplied at some point while an experiment is running, and submission-time arguments, requested in the build phase and set before the experiment is executed. For more on arguments in practice, see the tutorial section :ref:`mgmt-arguments`. For supported argument types, see the reference for :mod:`artiq.language.environment`; for specific methods, see the reference for :class:`~artiq.language.environment.HasEnvironment`.

.. _environment-datasets:

Datasets
--------

Datasets are values that are read and written by experiments kept in a key-value store. They exist to facilitate the exchange and preservation of information between experiments, from experiments to the management system, and from experiments to long-term storage. Datasets may be either scalars (``bool``, ``int``, ``float``, or NumPy scalar) or NumPy arrays. For basic use of datasets, see the :ref:`data interfaces tutorial <mgmt-datasets>`.

A dataset may be broadcast (``broadcast=True``), that is, distributed to all clients connected to the master. This is useful e.g. for the ARTIQ dashboard to plot results while an experiment is in progress and give rapid feedback to the user. Broadcasted datasets live in a global key-value store owned by the master. Care should be taken that experiments use distinctive real-time result names in order to avoid conflicts. Broadcasted datasets may be used to communicate values across experiments; for instance, a periodic calibration experiment might update a dataset read by payload experiments.

Broadcasted datasets are replaced when a new dataset with the same key (name) is produced. By default, they are erased when the master halts. Broadcasted datasets may be made persistent (``persistent=True``, which also implies ``broadcast=True``), in which case the master stores them in a LMDB database typically called ``dataset_db.mdb``, where they are saved across master restarts.

By default, datasets are archived in the ``results`` HDF5 output for that run, although this can be opted against (``archive=False``). They can be viewed and analyzed with the ARTIQ browser, or with an HDF5 viewer of your choice.

Datasets and units
^^^^^^^^^^^^^^^^^^

Datasets accept metadata for numerical formatting with the ``unit``, ``scale`` and ``precision`` parameters of ``set_dataset``.

.. note::
    In experiment code, values are assumed to be in the SI base unit. Setting a dataset with a value of ``1000`` and the unit ``kV`` represents the quantity ``1 kV``. It is recommended to use the globals defined by :mod:`artiq.language.units` and write ``1*kV`` instead of ``1000`` for the value.

    In dashboards and clients these globals are not available. However, setting a dataset with a value of ``1`` and the unit ``kV`` simply represents the quantity ``1 kV``.

    ``precision`` refers to the max number of decimal places to display. This parameter does not affect the underlying value, and is only used for display purposes.

