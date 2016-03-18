.. Add new releases at the top to keep important stuff directly visible.

Release notes
=============

Unreleased
----------

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
  it's arguments ``min/max`` have been renamed to ``start/stop`` respectively.
  Same for RandomScan (even though there direction matters little).
