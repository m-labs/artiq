Using DRTIO and subkernels
==========================

In larger or more spread-out systems, a single core device might not be suited to managing all the RTIO operations or channels necessary. For these situations ARTIQ supplies Distributed Real-Time IO, or DRTIO. This allows systems to be configured with some or all of their RTIO channels distributed to one or several *satellite* core devices, which are linked to the *master* core device. These remote channels are then accessible in kernels on the master device exactly like local channels.

While the components of a system, as well as the distribution of peripherals among satellites, are necessarily fixed in the system configuration, the specific topology of master and satellite links is flexible and can be changed whenever necessary. It is supplied to the core device by means of a routing table (see below). Kasli and Kasli-SoC devices use SFP ports for DRTIO connections. Links should be high-speed duplex serial lines operating 1Gbps or more.

Certain peripheral cards with onboard FPGAs of their own (e.g. Shuttler) can be configured as satellites in a DRTIO setting, allowing them to run their own subkernels and make use of DDMA. In these cases, the EEM connection to the core device is used for DRTIO communication (DRTIO-over-EEM).

.. note::
    As with other configuration changes (e.g. adding new hardware), if you are in possession of a non-distributed ARTIQ system and you'd like to expand it into a DRTIO setup, it's easily possible to do so, but you need to be sure that both master and satellite are (re)flashed with this in mind. As usual, if you obtained your hardware from M-Labs, you will normally be supplied with all the binaries you need, through :mod:`~artiq.frontend.afws_client` or otherwise.

.. warning::
    Do not confuse the DRTIO *master device* (used to mean the central controlling core device of a distributed system) with the *ARTIQ master* (the central piece of software of ARTIQ's management system, which interacts with :mod:`~artiq.frontend.artiq_client` and the dashboard.) :mod:`~artiq.frontend.artiq_run` can be used to run experiments on DRTIO systems just as easily as non-distributed ones, and the ARTIQ master interacts with the central core device regardless of whether it's configured as a DRTIO master or standalone.

Using DRTIO
-----------

.. _drtio-routing:

Configuring the routing table
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

By default, DRTIO assumes a routing table for a star topology (i.e. all satellites directly connected to the master), with destination 0 being the master device's local RTIO core and destinations 1 and above corresponding to devices on the master's respective downstream ports. To use any other topology, it is necessary to supply a corresponding routing table in the form of a binary file, written to flash storage under the key ``routing_table``. The binary file is easily generated in the correct format using :mod:`~artiq.frontend.artiq_route`. This example is for a chain of 3 devices: ::

    # create an empty routing table
    $ artiq_route rt.bin init

    # set destination 0 to the master's local RTIO core
    $ artiq_route rt.bin set 0 0

    # for destination 1, first use hop 1 (the first downstream port)
    # then use the local RTIO core of that second device.
    $ artiq_route rt.bin set 1 1 0

    # for destination 2, use hop 1 and reach the second device as
    # before, then use hop 1 on that device to reach the third
    # device, and finally use the local RTIO core (hop 0) of the
    # third device.
    $ artiq_route rt.bin set 2 1 1 0

    $ artiq_route rt.bin show
      0:   0
      1:   1   0
      2:   1   1   0

    $ artiq_coremgmt config write -f routing_table rt.bin

Destination numbers must correspond to the ones used in the :ref:`device database <device-db>`, listed in the ``satellite_cpu_targets`` field. If unsure which destination number corresponds to which physical satellite device, check the channel numbers of the peripherals associated with that device; in DRTIO systems bits 16-24 of the RTIO channel number correspond to the destination number of the core device they are bound to. See also the :doc:`drtio` page.

All routes must end with the local RTIO core of the destination device. Incorrect routing tables will cause ``RTIODestinationUnreachable`` exceptions. The local RTIO core of the master device is considered a destination like any other; it must be explicitly listed in the routing table to be accessible to kernels.

As with other configuration changes, the core device should be restarted (``artiq_coremgmt reboot``, power cycle, etc.) for changes to take effect.

Using the core language with DRTIO
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Remote channels are accessed just as local channels are (e.g., most commonly, by calling ``self.setattr_device()`` and then referencing the device by name.)

Link establishment
^^^^^^^^^^^^^^^^^^
After devices have booted, it takes several seconds for all links in a DRTIO system to become established. Kernels should not attempt to access destinations until all required links are up (trying to do so will raise ``RTIODestinationUnreachable`` exceptions). ARTIQ provides the method :meth:`~artiq.coredevice.core.Core.get_rtio_destination_status` which determines whether a destination can be reached. We recommend calling it in a loop in your startup kernel for each important destination in order to delay startup until they all can be reached.

Latency
^^^^^^^
Each hop (link traversed) increases the RTIO latency of a destination by a significant amount; however, this latency is constant and can be compensated for in kernels. To limit latency in a system, fully utilize the downstream ports of devices to reduce the depth of the tree, instead of creating chains. In some situations, the use of subkernels (see below) may also bypass potential latency issues.

Distributed Direct Memory Access (DDMA)
---------------------------------------

By default on DRTIO systems, all events recorded by the master's DMA core are kept and played back on the master. With distributed DMA, RTIO events that should be played back on remote destinations are distributed to the corresponding satellites. In some cases (typically, large buffers on several satellites with high event throughput), it allows for better performance and higher bandwidth, as the RTIO events do not have to be sent over the DRTIO link(s) during playback.

To enable distributed DMA for the master, simply provide an ``enable_ddma=True`` argument for the :meth:`~artiq.coredevice.dma.CoreDMA.record` method - taking a snippet from the non-distributed example in the :ref:`core language tutorial <getting-started-dma>`: ::

        @kernel
        def record(self):
            with self.core_dma.record("pulses", enable_ddma=True):
                # all RTIO operations now go to the "pulses"
                # DMA buffer, instead of being executed immediately.
                for i in range(50):
                    self.ttl0.pulse(100*ns)
                    delay(100*ns)

In standalone systems, as well as in subkernels (see below), this argument is ignored; in standalone systems it is meaningless and in subkernels it must always be enabled for structural reasons.

Enabling DDMA on a purely local sequence on a DRTIO system introduces an overhead during trace recording which comes from additional processing done on the record, so careful use is advised. Due to the extra time that communicating with relevant satellites takes, an additional delay before playback may be necessary to prevent a :exc:`~artiq.coredevice.exceptions.RTIOUnderflow` when playing back a DDMA-enabled sequence.

Subkernels
----------

Rather than only offloading the RTIO channels to satellites and limiting all processing to the master core device, it is also possible to run kernels directly on satellite devices. These are referred to as *subkernels*. Using subkernels to process and control remote RTIO channels can free up resources on the core device.

Subkernels behave for the most part like regular kernels; they accept arguments, can return values, and are marked by the decorator ``@subkernel(destination=i)``, where ``i`` is the satellite's destination number as used in the routing table. To call a subkernel, call it like any other function. There are however a few caveats:

   - subkernels do not support RPCs,
   - subkernels do not support (recursive) DRTIO (but they can call other subkernels and send messages to each other, see below),
   - they support DMA, for which DDMA is considered always enabled,
   - they can raise exceptions, which they may catch locally or propagate to the calling kernel,
   - their return values must be fully annotated with an ARTIQ type,
   - their arguments should be annotated, and only basic ARTIQ types are supported,
   - while ``self`` is allowed as an argument, it is retrieved at compile time and exists as a purely local object afterwards. Any changes made by other kernels will not be visible, and changes made locally will not be applied anywhere else.

Subkernels in practice
^^^^^^^^^^^^^^^^^^^^^^

Subkernels begin execution as soon as possible when called. By default, they are not awaited, but awaiting is necessary to receive results or exceptions. The await function ``subkernel_await(function, [timeout])`` takes as argument the subkernel to be awaited and, optionally, a timeout value in milliseconds. If the timeout is reached without response from the subkernel, a :exc:`~artiq.coredevice.exceptions.SubkernelError` is raised. If no timeout value is supplied the function waits indefinitely for the return. Negative timeout values are ignored.

For example, a subkernel performing integer addition: ::

    from artiq.experiment import *


    @subkernel(destination=1)
    def subkernel_add(a: TInt32, b: TInt32) -> TInt32:
        return a + b

    class SubkernelExperiment(EnvExperiment):
        def build(self):
            self.setattr_device("core")

        @kernel
        def run(self):
            subkernel_add(2, 2)
            result = subkernel_await(subkernel_add)
            assert result == 4

Subkernels are compiled after the main kernel and immediately sent to the designated satellite. When they are called, the master simply instructs the subkernel to load and run the corresponding kernel. When ``self`` is used in subkernels, it is embedded into the compiled and uploaded data; this is the reason why changes made do not propagate between kernels.

If a subkernel is called on a satellite where a kernel is already running, the newer kernel overrides silently, and the previous kernel will not be completed.

.. warning::
    Be careful with use of ``self.core.reset()`` around subkernels. Since ``self`` in subkernels is purely local, calling ``self.core.reset()`` in a subkernel will only affect that specific satellite and its own FIFOs. On the other hand, calling ``self.core.reset()`` in the master kernel will clear FIFOs in all satellites, regardless of whether a subkernel is running, but will not stop the subkernel. As a result, any event currently in a FIFO queue will be cleared, but the subkernels may continue to queue events. This is likely to result in odd behavior; it's best to avoid using ``self.core.reset()`` during the lifetime of any subkernels.

If a subkernel is complex and its binary relatively large, the delay between the call and actually running the subkernel may be substantial. If it's necessary to minimize this delay, ``subkernel_preload(function)`` should be used before the call.

Subkernels receive the value of the timeline cursor ``now_mu`` from the caller at the moment of the call. As there is a delay between calling the subkernel and its actual start, there will be a difference in ``now_mu`` that can be compensated with a delay in the subkernel. Additionally, preloading the subkernel would decrease the difference, as the subkernel does not have to be loaded before running.

While a subkernel is running, the satellite is disconnected from the RTIO interface of the master. As a result, regardless of what devices the subkernel itself uses, none of the RTIO devices on that satellite will be available to the master, nor will messages be passed on to any further satellites downstream. This applies both to regular RTIO operations and DDMA. While a subkernel is running, a satellite may use its own local DMA, but an attempt by any other device to run DDMA through the satellite will fail. Control is returned to the master when no subkernel is running -- to be sure that a device will be accessible, await before performing any RTIO operations on the affected satellite.

.. note::
    Subkernels do not exit automatically if a master kernel exits, and are seamlessly carried over between experiments. Much like RTIO events left in FIFO queues, the nature of seamless transition means subkernels left running after the end of an experiment cannot be guaranteed to complete (as they may be overriden by newer subkernels in the next experiment). Following experiments must also be aware of the risk of attempting to reach RTIO devices currently 'blocked' by an active subkernel left over from a previous experiment. This can be avoided simply by having each experiment await all of its subkernels at some point before exiting. Alternatively, if necessary, a system can be sanitized by calling trivial kernels in each satellite -- any leftover subkernels will be overriden and automatically cancelled.

Calling other kernels
^^^^^^^^^^^^^^^^^^^^^

Subkernels can call other kernels and subkernels. For a more complex example: ::

    from artiq.experiment import *

    class SubkernelExperiment(EnvExperiment):
        def build(self):
            self.setattr_device("core")
            self.setattr_device("ttl0")
            self.setattr_device("ttl8")  # assuming it's on satellite

        @subkernel(destination=1)
        def add_and_pulse(self, a: TInt32, b: TInt32) -> TInt32:
            c = a + b
            self.pulse_ttl(c)
            return c

        @subkernel(destination=1)
        def pulse_ttl(self, delay: TInt32) -> TNone:
            self.ttl8.pulse(delay*us)

        @kernel
        def run(self):
            subkernel_preload(self.add_and_pulse)
            self.core.reset()
            delay(10*ms)
            self.add_and_pulse(2, 2)
            self.ttl0.pulse(15*us)
            result = subkernel_await(self.add_and_pulse)
            assert result == 4
            self.pulse_ttl(20)

In this case, without the preload, the delay after the core reset would need to be longer. Depending on the connection, the call may still take some time in itself. Notice that the method ``pulse_ttl()`` can be called both within a subkernel and on its own.

.. note::
    Subkernels can call subkernels on any other satellite, not only their own. Care should however be taken that different kernels do not call subkernels on the same satellite, or only very cautiously. If, e.g., a newer call overrides a subkernel that another caller is awaiting, unpredictable timeouts or locks may result, as the original subkernel will never return. There is no mechanism to check whether a particular satellite is 'busy'; it is up to the programmer to handle this correctly.

Message passing
^^^^^^^^^^^^^^^

Apart from arguments and returns, subkernels can also pass messages between each other or the master with built-in ``subkernel_send()`` and ``subkernel_recv()`` functions. This can be used for communication between subkernels, to pass additional data, or to send partially computed data. Consider the following example: ::

    from artiq.experiment import *

    @subkernel(destination=1)
    def simple_message() -> TInt32:
        data = subkernel_recv("message", TInt32)
        return data + 20

    class MessagePassing(EnvExperiment):
        def build(self):
            self.setattr_device("core")

        @kernel
        def run(self):
            simple_self()
            subkernel_send(1, "message", 150)
            result = subkernel_await(simple_self)
            assert result == 170

The ``subkernel_send(destination, name, value)`` function requires three arguments: a destination, a name for the message (to be used for identification in the corresponding ``subkernel_recv()``), and the passed value.

The ``subkernel_recv(name, type, [timeout])`` function requires two arguments: message name (matching exactly the name provided in ``subkernel_send``) and expected type. Optionally, it also accepts a third argument, a timeout for the operation in milliseconds. As with ``subkernel_await``, the default behavior is to wait as long as necessary, and a negative argument is ignored.

A message can only be received while a subkernel is running, and is placed into a buffer to be retrieved when required. As a result ``send`` executes independently of any receive and never deadlocks. However, a ``receive`` function may timeout or lock (wait forever) if no message with the correct name and destination is ever sent.
