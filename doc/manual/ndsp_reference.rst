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

TDC001 controller usage example
+++++++++++++++++++++++++++++++

First, run the TDC001 controller::

    $ thorlabs_tcube_controller -P TDC001 -d /dev/ttyUSBx

.. note::
    On Windows the serial port (the ``-d`` argument) will be of the form ``COMx``.

Then, send commands to it via the ``artiq_rpctool`` utility::

    $ artiq_rpctool ::1 3255 list-targets
    Target(s):   tdc001
    $ artiq_rpctool ::1 3255 call move_relative 10000 # will move forward
    $ artiq_rpctool ::1 3255 call move_relative -10000 # will move backward
    $ artiq_rpctool ::1 3255 call move_absolute 20000 # absolute move to 20000
    $ artiq_rpctool ::1 3255 call move_home # will go back to home position
    $ artiq_rpctool ::1 3255 call close # close the device

TPZ001 controller usage example
+++++++++++++++++++++++++++++++

First, run the TPZ001 controller::

    $ thorlabs_tcube_controller -P TPZ001 -d /dev/ttyUSBx

.. note::
    On Windows the serial port (the ``-d`` argument) will be of the form ``COMx``.

Then, send commands to it via the ``artiq_rpctool`` utility::

    $ artiq_rpctool ::1 3255 list-targets
    Target(s):   tpz001
    $ artiq_rpctool ::1 3255 call set_output_volts 15 # set output voltage to 15 V
    $ artiq_rpctool ::1 3255 call get_output_volts # read back output voltage
    15
    $ artiq_rpctool ::1 3255 call set_tpz_io_settings 150 1 # set maximum output voltage to 150 V
    $ artiq_rpctool ::1 3255 call set_output_volts 150 # set output voltage to 150 V
    $ artiq_rpctool ::1 3255 call close # close the device

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
