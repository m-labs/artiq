Network device support packages reference
=========================================


PDQ2
----

Driver
++++++

.. automodule:: artiq.devices.pdq2.driver
    :members:

Mediator
++++++++

.. automodule:: artiq.devices.pdq2.mediator
    :members:

Controller
++++++++++

.. argparse::
   :ref: artiq.frontend.pdq2_controller.get_argparser
   :prog: pdq2_controller

Client
++++++

.. argparse::
   :ref: artiq.frontend.pdq2_client.get_argparser
   :prog: pdq2_client

Lab Brick Digital Attenuator (LDA)
----------------------------------

Driver
++++++

.. automodule:: artiq.devices.lda.driver
    :members:

Controller
++++++++++

.. argparse::
   :ref: artiq.frontend.lda_controller.get_argparser
   :prog: lda_controller

Novatech 409B
-------------

Driver
++++++

.. automodule:: artiq.devices.novatech409b.driver
    :members:

Controller
++++++++++

.. argparse::
   :ref: artiq.frontend.novatech409b_controller.get_argparser
   :prog: novatech409b_controller

Thorlabs T-Cube
---------------

TDC001 Driver
+++++++++++++

.. autoclass:: artiq.devices.thorlabs_tcube.driver.Tdc
    :members:

TPZ001 Driver
+++++++++++++

.. autoclass:: artiq.devices.thorlabs_tcube.driver.Tpz
    :members:

Controller
++++++++++

.. argparse::
    :ref: artiq.frontend.thorlabs_tcube_controller.get_argparser
    :prog: thorlabs_controller


Default TCP port list
---------------------

When writing a new NDSP, choose a free TCP port and add it to this list.

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
| Thorlabs T-Cube          | 3255         |
+--------------------------+--------------+
