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

On Linux, you need to give your user access to the usb device.

You can do that by creating a file under ``/etc/udev/rules.d/`` named
``99-lda.rules`` with the following content::

    SUBSYSTEM=="usb", ATTR{idVendor}=="041f", MODE="0666"

Then you need to tell udev to reload its rules::

    $ sudo invoke-rc.d udev reload

You must also unplug/replug your device if it was already plugged in.

Then, to run the Lab Brick Digital Attenuator (LDA) controller::

    $ lda_controller -d SN:xxxxx

The serial number must contain 5 digits, prepend any number of 0 necessary.
Also, the ``SN:`` prefix is mandatory.

You can chose the exact LDA model with the ``-P`` parameter. The default being LDA-102.

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


NI PXI6733
----------

PXI6733 controller usage example
++++++++++++++++++++++++++++++++

This controller has only been tested on Windows so far.

To use this controller you need first to install the NI-DAQmx driver
from http://www.ni.com/downloads/ni-drivers/f/.

Then you also need to install PyDAQmx python module::

    $ git clone https://github.com/clade/PyDAQmx
    $ cd PyDAQmx
    $ C:\Python34\Tools\Scripts\2to3.py -w .
    $ python setup.py build
    $ python setup.py install

Then, you can run the PXI6733 controller::

    $ pxi6733_controller -d Dev1

Then, send a load_sample_values command to it via the ``artiq_rpctool`` utility::

    $ artiq_rpctool ::1 3256 list-targets
    Target(s):   pxi6733
    $ artiq_rpctool ::1 3256 call load_sample_values 'np.array([1.0, 2.0, 3.0, 4.0], dtype=float)'

This loads 4 voltage values as a numpy float array: 1.0 V, 2.0 V, 3.0 V, 4.0 V

Then the device is set up to output those samples at each rising edge of the clock.

Driver
++++++

.. automodule:: artiq.devices.pxi6733.driver
    :members:

Controller
++++++++++

Usage example

.. argparse::
   :ref: artiq.frontend.pxi6733_controller.get_argparser
   :prog: pxi6733_controller

