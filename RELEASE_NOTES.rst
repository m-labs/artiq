.. Add new releases at the top to keep important stuff directly visible.

Release notes
=============

unreleased [2.x]
----------------

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


1.0rc2
------

* The CPU speed in the pipistrello gateware has been reduced from 83 1/3 MHz to
  75 MHz. This will reduce the achievable sustained pulse rate and latency
  accordingly. ISE was intermittently failing to meet timing (#341).
* set_dataset in broadcast mode no longer returns a Notifier. Mutating datasets
  should be done with mutate_dataset instead (#345).


1.0rc1
------

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
