.. Novatech 409B Artiq Driver documentation master file, created by
   sphinx-quickstart on Mon Nov 17 18:17:46 2014.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Novatech 409B 
=============

The `Novatech 409B`_ is a 4-channel direct digital synthesizer (DDS) 
made by novatech.com. 

.. _Novatech 409B: http://www.novatechsales.com/Bench-Signal-Generator.html

* DDS chipset is the 4-channel AD9959
 
* Frequency resolution: 0.1 Hz to 171 MHz (in 0.1 Hz steps)

* Phase resolution: 14-bit

* Amplitude: +4 dBm (digital attenuator is 10-bit resolution)

* RS-232 interface

    * 19.2 kBaud, 8 bits, 1 stop bit, no parity and no hardware flow control.


* External reference supported (10 MHz or 500 MHz) with option /R



=================
Artiq controller
=================

.. argparse::
    :ref: novatech409B-controller.define_parser
    :prog: fancytool

=================
Artiq client
=================

.. argparse::
    :ref: novatech409B-client.define_parser
    :prog: fancytool

=================
Novatech409B Class
=================

.. automodule :: novatech409B
    :members:

Contents:

.. toctree::
   :maxdepth: 2



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

