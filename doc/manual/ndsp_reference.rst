Network device support packages reference
=========================================

Core device logging controller
------------------------------

.. argparse::
   :ref: artiq.frontend.aqctl_corelog.get_argparser
   :prog: aqctl_corelog

PDQ2
----

Protocol
++++++++

.. automodule:: artiq.devices.pdq.protocol
    :members:

Driver
++++++

.. automodule:: artiq.devices.pdq.driver
    :members:

Mediator
++++++++

.. automodule:: artiq.devices.pdq.mediator
    :members:

Controller
++++++++++

.. argparse::
   :ref: artiq.frontend.aqctl_pdq.get_argparser
   :prog: aqctl_pdq


Lab Brick Digital Attenuator (LDA)
----------------------------------

Driver
++++++

.. automodule:: artiq.devices.lda.driver
    :members:

Controller
++++++++++

On Linux, you need to give your user access to the USB device.

You can do that by creating a file under ``/etc/udev/rules.d/`` named
``99-lda.rules`` with the following content::

    SUBSYSTEM=="usb", ATTR{idVendor}=="041f", MODE="0666"

Then you need to tell udev to reload its rules::

    $ sudo invoke-rc.d udev reload

You must also unplug/replug your device if it was already plugged in.

Then, to run the Lab Brick Digital Attenuator (LDA) controller::

    $ aqctl_lda -d SN:xxxxx

The serial number must contain exactly 5 digits, prepend it with the necessary number of 0s.
Also, the ``SN:`` prefix is mandatory.

You can choose the LDA model with the ``-P`` parameter. The default is LDA-102.

.. argparse::
   :ref: artiq.frontend.aqctl_lda.get_argparser
   :prog: aqctl_lda

Korad KA3005P
-------------

Driver
++++++

.. automodule:: artiq.devices.korad_ka3005p.driver
    :members:

Controller
++++++++++

.. argparse::
   :ref: artiq.frontend.aqctl_korad_ka3005p.get_argparser
   :prog: aqctl_korad_ka3005p

Novatech 409B
-------------

Driver
++++++

.. automodule:: artiq.devices.novatech409b.driver
    :members:

Controller
++++++++++

.. argparse::
   :ref: artiq.frontend.aqctl_novatech409b.get_argparser
   :prog: aqctl_novatech409b

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
