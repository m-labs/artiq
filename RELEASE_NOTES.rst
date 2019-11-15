.. Add new releases at the top to keep important stuff directly visible.

Release notes
=============

ARTIQ-6
-------

Highlights:

Breaking changes:


ARTIQ-5
-------

Highlights:

* Performance improvements:
   - Faster RTIO event submission (1.5x improvement in pulse rate test)
     See: https://github.com/m-labs/artiq/issues/636
   - Faster compilation times (3 seconds saved on kernel compilation time on a typical
     medium-size experiment)
     See: https://github.com/m-labs/artiq/commit/611bcc4db4ed604a32d9678623617cd50e968cbf
* Improved packaging and build system:
   - new continuous integration/delivery infrastructure based on Nix and Hydra,
     providing reproducibility, speed and independence.
   - rolling release process (https://github.com/m-labs/artiq/issues/1326).
   - firmware, gateware and device database templates are automatically built for all
     supported Kasli variants.
   - new JSON description format for generic Kasli systems.
   - Nix packages are now supported.
   - many Conda problems worked around.
   - controllers are now out-of-tree.
   - split packages that enable lightweight applications that communicate with ARTIQ,
     e.g. controllers running on non-x86 single-board computers.
* Improved Urukul support:
   - AD9910 RAM mode.
   - Configurable refclk divider and PLL bypass.
   - More reliable phase synchronization at high sample rates.
   - Synchronization calibration data can be read from EEPROM.
* A gateware-level input edge counter has been added, which offers higher
  throughput and increased flexibility over the usual TTL input PHYs where
  edge timestamps are not required. See `artiq.coredevice.edge_counter` for
  the core device driver and `artiq.gateware.rtio.phy.edge_counter`/
  `artiq.gateware.eem.DIO.add_std` for the gateware components.
* With DRTIO, Siphaser uses a better calibration mechanism.
  See: https://github.com/m-labs/artiq/commit/cc58318500ecfa537abf24127f2c22e8fe66e0f8
* Schedule updates can be sent to influxdb (artiq_influxdb_schedule).
* Experiments can now programatically set their default pipeline, priority, and flush flag.
* List datasets can now be efficiently appended to from experiments using
  `artiq.language.environment.HasEnvironment.append_to_dataset`.
* The core device now supports IPv6.
* To make development easier, the bootloader can receive firmware and secondary FPGA
  gateware from the network.
* Python 3.7 compatibility (Nix and source builds only, no Conda).
* Various other bugs from 4.0 fixed.
* Preliminary Sayma v2 and Metlino hardware support.

Breaking changes:

* The `artiq.coredevice.ad9910.AD9910` and
  `artiq.coredevice.ad9914.AD9914` phase reference timestamp parameters
  have been renamed to ``ref_time_mu`` for consistency, as they are in machine
  units.
* The controller manager now ignores device database entries without the
  ``command`` key set to facilitate sharing of devices between multiple
  masters.
* The meaning of the ``-d/--dir`` and ``--srcbuild`` options of ``artiq_flash``
  has changed.
* Controllers for third-party devices are now out-of-tree.
* ``aqctl_corelog`` now filters log messages below the ``WARNING`` level by default.
  This behavior can be changed using the ``-v`` and ``-q`` options like the other
  programs.
* On Kasli the firmware now starts with a unique default MAC address
  from EEPROM if `mac` is absent from the flash config.
* The ``-e/--experiment`` switch of ``artiq_run`` and ``artiq_compile``
  has been renamed ``-c/--class-name``.
* ``artiq_devtool`` has been removed.
* Much of ``artiq.protocols`` has been moved to a separate package ``sipyco``.
  ``artiq_rpctool`` has been renamed to ``sipyco_rpctool``.


ARTIQ-4
-------

4.0
***

* The ``artiq.coredevice.ttl`` drivers no longer track the timestamps of
  submitted events in software, requiring the user to explicitly specify the
  timeout for ``count()``/``timestamp_mu()``. Support for ``sync()`` has been dropped.

  Now that RTIO has gained DMA support, there is no longer a reliable way for
  the kernel CPU to track the individual events submitted on any one channel.
  Requiring the timeouts to be specified explicitly ensures consistent API
  behavior. To make this more convenient, the ``TTLInOut.gate_*()`` functions
  now return the cursor position at the end of the gate, e.g.::

    ttl_input.count(ttl_input.gate_rising(100 * us))

  In most situations – that is, unless the timeline cursor is rewound after the
  respective ``gate_*()`` call – simply passing ``now_mu()`` is also a valid
  upgrade path::

    ttl_input.count(now_mu())

  The latter might use up more timeline slack than necessary, though.

  In place of ``TTL(In)Out.sync``, the new ``Core.wait_until_mu()`` method can
  be used, which blocks execution until the hardware RTIO cursor reaches the
  given timestamp::

    ttl_output.pulse(10 * us)
    self.core.wait_until_mu(now_mu())
* RTIO outputs use a new architecture called Scalable Event Dispatcher (SED),
  which allows building systems with large number of RTIO channels more
  efficiently.
  From the user perspective, collision errors become asynchronous, and non-
  monotonic timestamps on any combination of channels are generally allowed
  (instead of producing sequence errors).
  RTIO inputs are not affected.
* The DDS channel number for the NIST CLOCK target has changed.
* The dashboard configuration files are now stored one-per-master, keyed by the
  server address argument and the notify port.
* The master now has a ``--name`` argument. If given, the dashboard is labelled
  with this name rather than the server address.
* ``artiq_flash`` targets Kasli by default. Use ``-t kc705`` to flash a KC705
  instead.
* ``artiq_flash -m/--adapter`` has been changed to ``artiq_flash -V/--variant``.
* The ``proxy`` action of ``artiq_flash`` is determined automatically and should
  not be specified manually anymore.
* ``kc705_dds`` has been renamed ``kc705``.
* The ``-H/--hw-adapter`` option of ``kc705`` has been renamed ``-V/--variant``.
* SPI masters have been switched from misoc-spi to misoc-spi2. This affects
  all out-of-tree RTIO core device drivers using those buses. See the various
  commits on e.g. the ``ad53xx`` driver for an example how to port from the old
  to the new bus.
* The ``ad5360`` coredevice driver has been renamed to ``ad53xx`` and the API
  has changed to better support Zotino.
* ``artiq.coredevice.dds`` has been renamed to ``artiq.coredevice.ad9914`` and
  simplified. DDS batch mode is no longer supported. The ``core_dds`` device
  is no longer necessary.
* The configuration entry ``startup_clock`` is renamed ``rtio_clock``. Switching
  clocks dynamically (i.e. without device restart) is no longer supported.
* ``set_dataset(..., save=True)`` has been renamed
  ``set_dataset(..., archive=True)``.
* On the AD9914 DDS, when switching to ``PHASE_MODE_CONTINUOUS`` from another mode,
  use the returned value of the last ``set_mu`` call as the phase offset for
  ``PHASE_MODE_CONTINUOUS`` to avoid a phase discontinuity. This is no longer done
  automatically. If one phase glitch when entering ``PHASE_MODE_CONTINUOUS`` is not
  an issue, this recommendation can be ignored.


ARTIQ-3
-------

3.7
***

No further notes.


3.6
***

No further notes.


3.5
***

No further notes.


3.4
***

No further notes.


3.3
***

No further notes.


3.2
***

* To accommodate larger runtimes, the flash layout as changed. As a result, the
  contents of the flash storage will be lost when upgrading. Set the values back
  (IP, MAC address, startup kernel, etc.) after the upgrade.


3.1
***

No further notes.


3.0
***

* The ``--embed`` option of applets is replaced with the environment variable
  ``ARTIQ_APPLET_EMBED``. The GUI sets this enviroment variable itself and the
  user simply needs to remove the ``--embed`` argument.
* ``EnvExperiment``'s ``prepare`` calls ``prepare`` for all its children.
* Dynamic ``__getattr__``'s returning RPC target methods are not supported anymore.
  Controller driver classes must define all their methods intended for RPC as
  members.
* Datasets requested by experiments are by default archived into their HDF5
  output. If this behavior is undesirable, turn it off by passing
  ``archive=False`` to ``get_dataset``.
* ``seconds_to_mu`` and ``mu_to_seconds`` have become methods of the core
  device driver (use e.g. ``self.core.seconds_to_mu()``).
* AD9858 DDSes and NIST QC1 hardware are no longer supported.
* The DDS class names and setup options have changed, this requires an update of
  the device database.
* ``int(a, width=b)`` has been removed. Use ``int32(a)`` and ``int64(a)``.
* The KC705 gateware target has been renamed ``kc705_dds``.
* ``artiq.coredevice.comm_tcp`` has been renamed ``artiq.coredevice.comm_kernel``,
  and ``Comm`` has been renamed ``CommKernel``.
* The "collision" and "busy" RTIO errors are reported through the log instead of
  raising exceptions.
* Results are still saved when ``analyze`` raises an exception.
* ``LinearScan`` and ``RandomScan`` have been consolidated into RangeScan.
* The Pipistrello is no longer supported. For a low-cost ARTIQ setup, use either
  ARTIQ 2.x with Pipistrello, or the future ARTIQ 4.x with Kasli. Note that the
  Pipistrello board has also been discontinued by the manufacturer but its design
  files are freely available.
* The device database is now generated by an executable Python script. To migrate
  an existing database, add ``device_db = `` at the beginning, and replace any PYON
  identifiers (``true``, ``null``, ...) with their Python equivalents
  (``True``, ``None`` ...).
* Controllers are now named ``aqctl_XXX`` instead of ``XXX_controller``.
* In the device database, the ``comm`` device has been folded into the ``core`` device.
  Move the "host" argument into the ``core`` device, and remove the ``comm`` device.
* The core device log now contains important information about events such as
  RTIO collisions. A new controller ``aqctl_corelog`` must be running to forward
  those logs to the master. See the example device databases to see how to
  instantiate this controller. Using ``artiq_session`` ensures that a controller
  manager is running simultaneously with the master.
* Experiments scheduled with the "flush pipeline" option now proceed when there
  are lower-priority experiments in the pipeline. Only experiments at the current
  (or higher) priority level are flushed.
* The PDQ(2/3) driver has been removed and is now being maintained out-of tree
  at https://github.com/m-labs/pdq. All SPI/USB driver layers, Mediator,
  CompoundPDQ and examples/documentation has been moved.
* The master now rotates log files at midnight, rather than based on log size.
* The results keys ``start_time`` and ``run_time`` are now stored as doubles of UNIX time,
  rather than ints. The file names are still based on local time.
* Packages are no longer available for 32-bit Windows.


ARTIQ-2
-------

2.5
***

No further notes.


2.4
***

No further notes.


2.3
***

* When using conda, add the conda-forge channel before installing ARTIQ.


2.2
***

No further notes.


2.1
***

No further notes.


2.0
***

No further notes.


2.0rc2
******

No further notes.


2.0rc1
******

* The format of the influxdb pattern file is simplified. The procedure to
  edit patterns is also changed to modifying the pattern file and calling:
  ``artiq_rpctool.py ::1 3248 call scan_patterns`` (or restarting the bridge)
  The patterns can be converted to the new format using this code snippet::

    from artiq.protocols import pyon
    patterns = pyon.load_file("influxdb_patterns.pyon")
    for p in patterns:
        print(p)

* The "GUI" has been renamed the "dashboard".
* When flashing NIST boards, use "-m nist_qcX" or "-m nist_clock" instead of
  just "-m qcX" or "-m clock" (#290).
* Applet command lines now use templates (e.g. $python) instead of formats
  (e.g. {python}).
* On Windows, GUI applications no longer open a console. For debugging
  purposes, the console messages can still be displayed by running the GUI
  applications this way::

    python3.5 -m artiq.frontend.artiq_browser
    python3.5 -m artiq.frontend.artiq_dashboard

  (you may need to replace python3.5 with python)
  Please always include the console output when reporting a GUI crash.
* The result folders are formatted "%Y-%m-%d/%H instead of "%Y-%m-%d/%H-%M".
  (i.e. grouping by day and then by hour, instead of by day and then by minute)
* The ``parent`` keyword argument of ``HasEnvironment`` (and ``EnvExperiment``)
  has been replaced. Pass the parent as first argument instead.
* During experiment examination (and a fortiori repository scan), the values of
  all arguments are set to ``None`` regardless of any default values supplied.
* In the dashboard's experiment windows, partial or full argument recomputation
  takes into account the repository revision field.
* By default, ``NumberValue`` and ``Scannable`` infer the scale from the unit
  for common units.
* By default, artiq_client keeps the current persist flag on the master.
* GUI state files for the browser and the dashboard are stores in "standard"
  locations for each operating system. Those are
  ``~/.config/artiq/2/artiq_*.pyon`` on Linux and
  ``C:\Users\<username>\AppData\Local\m-labs\artiq\2\artiq_*.pyon`` on
  Windows 7.
* The position of the time cursor is kept across experiments and RTIO resets
  are manual and explicit (inter-experiment seamless handover).
* All integers manipulated by kernels are numpy integers (numpy.int32,
  numpy.int64). If you pass an integer as a RPC argument, the target function
  receives a numpy type.


ARTIQ-1
-------

1.3
***

No further notes.


1.2
***

No further notes.


1.1
***

* TCA6424A.set converts the "outputs" value to little-endian before programming
  it into the registers.


1.0
***

No further notes.


1.0rc4
******

* setattr_argument and setattr_device add their key to kernel_invariants.


1.0rc3
******

* The HDF5 format has changed.

  * The datasets are located in the HDF5 subgroup ``datasets``.
  * Datasets are now stored without additional type conversions and annotations
    from ARTIQ, trusting that h5py maps and converts types between HDF5 and
    python/numpy "as expected".

* NumberValue now returns an integer if ``ndecimals`` = 0, ``scale`` = 1 and
  ``step`` is integer.


1.0rc2
******

* The CPU speed in the pipistrello gateware has been reduced from 83 1/3 MHz to
  75 MHz. This will reduce the achievable sustained pulse rate and latency
  accordingly. ISE was intermittently failing to meet timing (#341).
* set_dataset in broadcast mode no longer returns a Notifier. Mutating datasets
  should be done with mutate_dataset instead (#345).


1.0rc1
******

* Experiments (your code) should use ``from artiq.experiment import *``
  (and not ``from artiq import *`` as previously)
* Core device flash storage has moved due to increased runtime size.
  This requires reflashing the runtime and the flash storage filesystem image
  or erase and rewrite its entries.
* ``RTIOCollisionError`` has been renamed to ``RTIOCollision``
* the new API for DDS batches is::

    with self.core_dds.batch:
       ...

  with ``core_dds`` a device of type ``artiq.coredevice.dds.CoreDDS``.
  The dds_bus device should not be used anymore.
* LinearScan now supports scanning from high to low. Accordingly,
  its arguments ``min/max`` have been renamed to ``start/stop`` respectively.
  Same for RandomScan (even though there direction matters little).
