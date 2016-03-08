Release notes
=============

1.0 (unreleased)
----------------

* First release
* Experiments (your code) should use ``from artiq.experiment import *``
  (and not ``from artiq import *`` as previously)
* Core device flash storage has moved due to increased runtime size.
  This requires reflashing the runtime and the flash storage filesystem image
  or erase and rewrite its entries.
* RTIOCollisionError has been renamed to RTIOCollision
 