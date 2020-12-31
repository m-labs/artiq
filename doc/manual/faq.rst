.. Copyright (C) 2014, 2015 Robert Jordens <jordens@gmail.com>

FAQ
###

How do I ...
============

find ARTIQ examples?
--------------------

The examples are installed in the ``examples`` folder of the ARTIQ package. You can find where the ARTIQ package is installed on your machine with: ::

  python3 -c "import artiq; print(artiq.__path__[0])"

Copy the ``examples`` folder from that path into your home/user directory, and start experimenting!

prevent my first RTIO command from causing an underflow?
--------------------------------------------------------

The first RTIO event is programmed with a small timestamp above the value of the timecounter when the core device is reset. If the kernel needs more time than this timestamp to produce the event, an underflow will occur. You can prevent it by calling ``break_realtime`` just before programming the first event, or by adding a sufficient delay.

If you are not resetting the core device, the time cursor stays where the previous experiment left it.

organize datasets in folders?
-----------------------------

Use the dot (".") in dataset names to separate folders. The GUI will automatically create and delete folders in the dataset tree display.

write a generator feeding a kernel feeding an analyze function?
---------------------------------------------------------------

  Like this::

    def run(self):
        self.parse(self.pipe(iter(range(10))))

    def pipe(self, gen):
        for i in gen:
            r = self.do(i)
            yield r

    def parse(self, gen):
        for i in gen:
            pass

    @kernel
    def do(self, i):
        return i

create and use variable lengths arrays in kernels?
--------------------------------------------------

Don't. Preallocate everything. Or chunk it and e.g. read 100 events per
function call, push them upstream and retry until the gate time closes.

execute multiple slow controller RPCs in parallel without losing time? 
----------------------------------------------------------------------

Use ``threading.Thread``: portable, fast, simple for one-shot calls.

write part of my experiment as a coroutine/asyncio task/generator?
------------------------------------------------------------------

You can not change the API that your experiment exposes: ``build()``,
``prepare()``, ``run()`` and ``analyze()`` need to be regular functions, not
generators or asyncio coroutines. That would make reusing your own code in
sub-experiments difficult and fragile. You can however wrap your own
generators/coroutines/tasks in regular functions that you then expose as part
of the API.

determine the pyserial URL to attach to a device by its serial number?
----------------------------------------------------------------------

You can list your system's serial devices and print their vendor/product
id and serial number by running::

    $ python3 -m serial.tools.list_ports -v

It will give you the ``/dev/ttyUSBxx`` (or the ``COMxx`` for Windows) device
names.
The ``hwid:`` field gives you the string you can pass via the ``hwgrep://``
feature of pyserial
`serial_for_url() <http://pyserial.sourceforge.net/pyserial_api.html#serial.serial_for_url>`_
in order to open a serial device.

The preferred way to specify a serial device is to make use of the ``hwgrep://``
URL: it allows to select the serial device by its USB vendor ID, product
ID and/or serial number. Those never change, unlike the device file name.

For instance, if you want to specify the Vendor/Product ID and the USB Serial Number, you can do:

``-d "hwgrep://<VID>:<PID> SNR=<serial_number>"``.
for example:

``-d "hwgrep://0403:faf0 SNR=83852734"``


run unit tests?
---------------

The unit tests assume that the Python environment has been set up in such a way that ``import artiq`` will import the code being tested, and that this is still true for any subprocess created. This is not the way setuptools operates as it adds the path to ARTIQ to ``sys.path`` which is not passed to subprocesses; as a result, running the tests via ``setup.py`` is not supported. The user must first install the package or set ``PYTHONPATH``, and then run the tests with e.g. ``python3 -m unittest discover`` in the ``artiq/test`` folder and ``lit .`` in the ``artiq/test/lit`` folder.

For the hardware-in-the-loop unit tests, set the ``ARTIQ_ROOT`` environment variable to the path to a device database containing the relevant devices.

The core device tests require the following TTL devices and connections:

* ``ttl_out``: any output-only TTL.
* ``ttl_out_serdes``: any output-only TTL that uses a SERDES (i.e. has a fine timestamp). Can be aliased to ``ttl_out``.
* ``loop_out``: any output-only TTL. Must be physically connected to ``loop_in``. Can be aliased to ``ttl_out``.
* ``loop_in``: any input-capable TTL. Must be physically connected to ``loop_out``.
* ``loop_clock_out``: a clock generator TTL. Must be physically connected to ``loop_clock_in``.
* ``loop_clock_in``: any input-capable TTL. Must be physically connected to ``loop_clock_out``.

If TTL devices are missing, the corresponding tests are skipped.

find the dashboard and browser configuration files are stored?
--------------------------------------------------------------

::
  python -c "from artiq.tools import get_user_config_dir; print(get_user_config_dir())"
