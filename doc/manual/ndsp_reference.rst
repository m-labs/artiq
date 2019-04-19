Network device support packages reference
=========================================

Core device logging controller
------------------------------

.. argparse::
   :ref: artiq.frontend.aqctl_corelog.get_argparser
   :prog: aqctl_corelog


Thorlabs T-Cube
---------------

.. note::
    When power is applied before the USB connection, some devices will enter a state where they fail to report the completion of commands. When using the ARTIQ controller, this cause certain function calls to never return and freeze the controller. To prevent this, connect USB first and then power up the device. When a device has entered the problematic state, power-cycling it while keeping the USB connection active also resolves the problem.

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
    :ref: artiq.frontend.aqctl_thorlabs_tcube.get_argparser
    :prog: aqctl_thorlabs

.. _tdc001-controller-usage-example:

TDC001 controller usage example
+++++++++++++++++++++++++++++++

First, run the TDC001 controller::

    $ aqctl_thorlabs_tcube -P TDC001 -d /dev/ttyUSBx

.. note::
    On Windows the serial port (the ``-d`` argument) will be of the form ``COMx``.

.. note::
    Anything compatible with `serial_for_url <http://pyserial.sourceforge.net/pyserial_api.html#serial.serial_for_url>`_
    can be given as a device in ``-d`` argument.

    For instance, if you want to specify the Vendor/Product ID and the USB Serial Number, you can do:

    ``-d "hwgrep://<VID>:<PID> SNR=<serial_number>"``.
    for instance:

    ``-d "hwgrep://0403:faf0 SNR=83852734"``

    The hwgrep URL works on both Linux and Windows.

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

    $ aqctl_thorlabs_tcube -P TPZ001 -d /dev/ttyUSBx

.. note::
    On Windows the serial port (the ``-d`` argument) will be of the form ``COMx``.

.. note::
    See the :ref:`TDC001 documentation <tdc001-controller-usage-example>` for
    how to specify the USB Serial Number of the device instead of the
    /dev/ttyUSBx (or the COMx name).

Then, send commands to it via the ``artiq_rpctool`` utility::

    $ artiq_rpctool ::1 3255 list-targets
    Target(s):   tpz001
    $ artiq_rpctool ::1 3255 call set_output_volts 15 # set output voltage to 15 V
    $ artiq_rpctool ::1 3255 call get_output_volts # read back output voltage
    15
    $ artiq_rpctool ::1 3255 call set_tpz_io_settings 150 1 # set maximum output voltage to 150 V
    $ artiq_rpctool ::1 3255 call set_output_volts 150 # set output voltage to 150 V
    $ artiq_rpctool ::1 3255 call close # close the device
