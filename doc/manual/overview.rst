Overview diagram
================

.. Kept in a separate file for the luxury of good syntax highlighting

.. tikz:: Structure of an ARTIQ system. Note that most components can also be used independently of each other. Network-connected components can be distributed across multiple machines.
   :align: left
   :libs: positioning, shapes, arrows
   :xscale: 100
   :include: overview.tex

Footnotes:

   1. As described in the :doc:`management tutorial <getting_started_mgmt>`, the clients can simply be run on the same machine as the master. It is common however to set up several other 'client machines' to allow distributed access to the system, each with an installation of ARTIQ and (potentially) a Git clone of the experiment repository. The communication between components is the same. Other ARTIQ commands and utilities can also be used from these machines.

   2. It is common to have controllers for one or several 'slow' devices running on other machines. In this case, it's simply necessary to have one controller manager per machine. Note that running controllers and controller managers does not require a full ARTIQ install: the minimal package ``artiq-comtools`` can be installed instead. Otherwise, if these controllers are run side-by-side to the built-in controllers, they can be handled by the same controller manager, as depicted by the non-dashed lines.

   3. The various other ARTIQ utilities may also connect to the master, read the device database, communicate with the core device, etc., depending on their specific functionalities. See their :doc:`individual references <utilities>`.

   4. These are the :ref:`built-in controllers <built-in-ctlrs>` used by the ARTIQ dashboard to provide certain functionalities which require access to the core device. They can be found listed in :ref:`Utilities <utilities-ctrls>` (the commands prefixed with ``aqctl_`` rather than ``artiq_``). It is possible to use the ARTIQ management system without them, and the other abilities of the dashboard will still function, but important features will be unavailable.
