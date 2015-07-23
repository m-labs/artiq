FAQ
###

How do I ...
============

prevent my first RTIO command from causing an underflow?
--------------------------------------------------------

The first RTIO event is programmed with a small timestamp above the value of the timecounter at the start of the experiment. If the kernel needs more time than this timestamp to produce the event, an underflow will occur. You can prevent it by calling ``break_realtime`` just before programming the first event, or by adding a sufficient delay.

organize parameters in folders?
-------------------------------

Folders are not supported yet, use GUI filtering for now. Names need to be unique.

enforce functional dependencies between parameters?
---------------------------------------------------

If you want to override a parameter ``b`` in the PDB to be ``b = 2*a``,
use wrapper experiments, overriding parameters by passing them to the
experiment's constructor (``param_override`` argument).

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

You can not change the API that your experiment exposes: ``__init__()``,
``build()``, ``run()`` and ``analyze()`` need to be regular functions, not
generators or asyncio coroutines. That would make reusing your own code in
sub-experiments difficult and fragile. You can however always use the
scheduler API to achieve the same (``scheduler.yield(duration=0)``)
or wrap your own generators/coroutines/tasks in regular functions that
you then expose as part of the API.

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

See the :ref:`TDC001 documentation <tdc001-controller-usage-example>` for an example of ``hwgrep://`` usage.
