Drivers reference
=================

These drivers are for "slow" devices that are directly controlled by a PC, typically over a non-realtime channel such as USB.

Certain devices (such as the PDQ2) may still perform real-time operations by having certain controls physically connected to the core device (for example, the trigger and frame selection signals on the PDQ2). For handling such cases, parts of the drivers may be kernels executed on the core device.

Each driver is run in a separate "controller" that exposes a RPC interface (based on :class:`artiq.protocols.pc_rpc`) to its functions. The master never does direct I/O to the devices, but issues RPCs to the controllers when needed. As opposed to running everything on the master, this architecture has those main advantages:

* Each driver can be run on a different machine, which alleviates cabling issues and OS compatibility problems.
* Reduces the impact of driver crashes.
* Reduces the impact of driver memory leaks.

:mod:`artiq.devices.pdq2` module
----------------------------------

.. automodule:: artiq.devices.pdq2
    :members:

.. argparse::
   :ref: artiq.frontend.pdq2_controller.get_argparser
   :prog: pdq2_controller

.. argparse::
   :ref: artiq.frontend.pdq2_client.get_argparser
   :prog: pdq2_client

:mod:`artiq.devices.lda` module
---------------------------------

.. automodule:: artiq.devices.lda.driver
    :members:

.. argparse::
   :ref: artiq.frontend.lda_controller.get_argparser
   :prog: lda_controller

Default TCP port list
---------------------

When writing a new driver, choose a free TCP port and add it to this list.

+--------------------------+--------------+
| Component                | Default port |
+==========================+==============+
| Master (notifications)   | 3250         |
+--------------------------+--------------+
| Master (control)         | 3251         |
+--------------------------+--------------+
| PDQ2                     | 3252         |
+--------------------------+--------------+
| LDA                      | 3253         |
+--------------------------+--------------+
| Novatech 409B            | 3254         |
+--------------------------+--------------+
