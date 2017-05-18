Utilities
=========

.. Sort these tool by some subjective combination of their
   typical sequence and expected frequency of use.


Local running tool
------------------

.. argparse::
   :ref: artiq.frontend.artiq_run.get_argparser
   :prog: artiq_run

Remote Procedure Call tool
--------------------------

.. argparse::
   :ref: artiq.frontend.artiq_rpctool.get_argparser
   :prog: artiq_rpctool

This tool is the preferred way of handling simple ARTIQ controllers.
Instead of writing a client for very simple cases you can just use this tool
in order to call remote functions of an ARTIQ controller.

* Listing existing targets

        The ``list-targets`` sub-command will print to standard output the
        target list of the remote server::

            $ artiq_rpctool hostname port list-targets

* Listing callable functions

        The ``list-methods`` sub-command will print to standard output a sorted
        list of the functions you can call on the remote server's target.

        The list will contain function names, signatures (arguments) and
        docstrings.

        If the server has only one target, you can do::

            $ artiq_rpctool hostname port list-methods

        Otherwise you need to specify the target, using the ``-t target``
        option::

            $ artiq_rpctool hostname port list-methods -t target_name

* Remotely calling a function

        The ``call`` sub-command will call a function on the specified remote
        server's target, passing the specified arguments.
        Like with the previous sub-command, you only need to provide the target
        name (with ``-t target``) if the server hosts several targets.

        The following example will call the ``set_attenuation`` method of the
        Lda controller with the argument ``5``::

            $ artiq_rpctool ::1 3253 call -t lda set_attenuation 5

        In general, to call a function named ``f`` with N arguments named
        respectively ``x1, x2, ..., xN`` you can do::

            $ artiq_rpctool hostname port call -t target f x1 x2 ... xN

        You can use Python syntax to compute arguments as they will be passed
        to the ``eval()`` primitive. The numpy package is available in the namespace
        as ``np``. Beware to use quotes to separate arguments which use spaces::

            $ artiq_rpctool hostname port call -t target f '3 * 4 + 2' True '[1, 2]'
            $ artiq_rpctool ::1 3256 call load_sample_values 'np.array([1.0, 2.0], dtype=float)'

        If the called function has a return value, it will get printed to
        the standard output if the value is not None like in the standard
        python interactive console::

            $ artiq_rpctool ::1 3253 call get_attenuation
            5.0 dB

Static compiler
---------------

This tool compiles an experiment into a ELF file. It is primarily used to prepare binaries for the default experiment loaded in non-volatile storage of the core device.
Experiments compiled with this tool are not allowed to use RPCs, and their ``run`` entry point must be a kernel.

.. argparse::
   :ref: artiq.frontend.artiq_compile.get_argparser
   :prog: artiq_compile

Flash storage image generator
-----------------------------

This tool compiles key/value pairs into a binary image suitable for flashing into the flash storage space of the core device.

.. argparse::
   :ref: artiq.frontend.artiq_mkfs.get_argparser
   :prog: artiq_mkfs

Flashing/Loading tool
---------------------

.. argparse::
   :ref: artiq.frontend.artiq_flash.get_argparser
   :prog: artiq_flash

.. _core-device-configuration-tool:

Core device configuration tool
------------------------------

The artiq_coreconfig utility gives remote access to the :ref:`core-device-flash-storage`.

To use this tool, you need to specify a ``device_db.py`` device database file which contains a ``comm`` device (an example is provided in ``examples/master/device_db.py``). This tells the tool how to connect to the core device and with which parameters (e.g. IP address, TCP port). When not specified, the artiq_coreconfig utility will assume that there is a file named ``device_db.py`` in the current directory.

To read the record whose key is ``mac``::

    $ artiq_coreconfig read mac

To write the value ``test_value`` in the key ``my_key``::

    $ artiq_coreconfig write -s my_key test_value
    $ artiq_coreconfig read my_key
    b'test_value'

You can also write entire files in a record using the ``-f`` parameter. This is useful for instance to write the startup and idle kernels in the flash storage::

    $ artiq_coreconfig write -f idle_kernel idle.elf
    $ artiq_coreconfig read idle_kernel | head -c9
    b'\x7fELF

You can write several records at once::

    $ artiq_coreconfig write -s key1 value1 -f key2 filename -s key3 value3

To remove the previously written key ``my_key``::

    $ artiq_coreconfig delete my_key

You can remove several keys at once::

    $ artiq_coreconfig delete key1 key2

To erase the entire flash storage area::

    $ artiq_coreconfig erase

You do not need to remove a record in order to change its value, just overwrite it::

    $ artiq_coreconfig write -s my_key some_value
    $ artiq_coreconfig write -s my_key some_other_value
    $ artiq_coreconfig read my_key
    b'some_other_value'

.. argparse::
   :ref: artiq.frontend.artiq_coreconfig.get_argparser
   :prog: artiq_coreconfig

Core device log download tool
-----------------------------

.. argparse::
   :ref: artiq.frontend.artiq_corelog.get_argparser
   :prog: artiq_corelog

.. _core-device-rtio-analyzer-tool:

Core device RTIO analyzer tool
------------------------------

.. argparse::
   :ref: artiq.frontend.artiq_coreanalyzer.get_argparser
   :prog: artiq_coreanalyzer

Data to InfluxDB bridge
-----------------------

.. argparse::
   :ref: artiq.frontend.artiq_influxdb.get_argparser
   :prog: artiq_influxdb
