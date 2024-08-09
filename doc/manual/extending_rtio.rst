Extending RTIO
==============

.. warning::

    This page is for users who want to extend or modify ARTIQ RTIO. Broadly speaking, one of the core intentions of ARTIQ is to provide a high-level, easy-to-use interface for experimentation, while the infrastructure handles the technological challenges of the high-resolution, timing-critical operations required. Rather than worrying about the details of timing in hardware, users can outline tasks quickly and efficiently in ARTIQ Python, and trust the system to carry out those tasks in real time. It is not normally, or indeed ever, necessary to make modifications on a gateware level.

    However, ARTIQ is an open-source project, and welcomes interest and agency from its users, as well as from experienced developers. This page is intended to serve firstly as a broad introduction to the internal structure of ARTIQ, and secondly as a tutorial for how RTIO extensions in ARTIQ can be made. Experience with FPGAs or hardware description languages is not strictly necessary, but additional research on the topic will likely be required to make serious modifications of your own.

    For instructions on setting up the ARTIQ development environment and on building gateware and firmware binaries, first see :doc:`building_developing` in the main part of the manual.

Introduction to the ARTIQ internal stack
----------------------------------------

.. tikz::
   :align: center
   :libs: positioning, arrows.meta
   :xscale: 70

    \definecolor{primary}{HTML}{0d3547} % ARTIQ blue

    \pgfdeclarelayer{bg}    % declare background layer
    \pgfsetlayers{bg,main}  % set layer order

    \node[draw, dotted, thick] (frontend) at (0, 6) {Host machine: Compiler, master, GUI...};

    \node[draw=primary, fill=white] (software) at (0, 5) {Software: \it{Kernel code}};
    \node[draw=blue, fill=white, thick] (firmware) at (0, 4) {Firmware: \it{ARTIQ runtime}};
    \node[draw=blue, fill=white, thick] (gateware) at (0, 3) {Gateware: \it{Migen and Misoc}};
    \node[draw=primary, fill=white] (hardware) at (0, 2) {Hardware: \it{Sinara ecosystem}};

    \begin{pgfonlayer}{bg}
        \draw[primary, -{Stealth}, dotted, thick] (frontend.south) to [out=-180, in=-180] (firmware.west);
        \draw[primary, -{Stealth}, dotted, thick] (frontend) to (software);
    \end{pgfonlayer}
    \draw[primary, -{Stealth}] (firmware) to (software);
    \draw[primary, -{Stealth}] (gateware) to (firmware);
    \draw[primary, -{Stealth}] (hardware) to (gateware);

Like any other modern piece of software, kernel code running on an ARTIQ core device rests upon a layered infrastructure, starting with the hardware: the physical carrier board and its peripherals. Generally, though not exclusively, this is the `Sinara device family <https://m-labs.hk/experiment-control/sinara-core/>`_, which is designed to work with ARTIQ. Other carrier boards, such as the Xilinx KC705 and ZC706, are also supported.

All ARTIQ of the ore device carrier boards necessarily center around a physical field-programmable gate array, or FPGA. If you have never worked with FPGAs before, it is easiest to understand them as 'rearrangeable' circuits. Ideally, they are capable of the tremendous speed and reliability advantages of custom-designed, application-specific hardware, while still being reprogrammable, allowing development and revision to continue after manufacturing.

The 'configuration' of an FPGA, the circuit design it is programmed with, is its *gateware*. Gateware is not software, and is not written in programming languges. Rather, it is written in a *hardware description language,* of which the most common are VHDL and Verilog. The ARTIQ codebase uses a set of tools called `Migen <https://m-labs.hk/gateware/migen/>`_ to write hardware description in a subset of Python, which is later translated to Verilog behind the scenes. This has the advantage of preserving much of the flexibility and convenience of Python as a programming language, but shouldn't be mistaken for it *being* Python, or functioning like Python. (MiSoC, built on Migen, is used to implement softcore -- i.e. 'programmed', on-FPGA, not hardwired -- CPUs on Kasli and KC75. Zynq devices contain 'hardcore' ARM CPUs already and correspondingly make less intensive use of MiSoC.)

The low-level software that runs directly on the core device's CPU, softcore or hardcore, is its *firmware.* This is the 'operating system' of the core device. The firmware is tasked, among other things, with handling the low-level communication between core devices, as well as between the core device and the host machine. It is written in bare-metal `Rust <https://www.rust-lang.org/>`__. There are currently two active versions of the ARTIQ firmware (the form used for ARTIQ-Zynq, NAR3, is more modern than that used on Kasli and KC705, and will eventually replace it) but they are largely equivalent except for internal details.

Experiment kernels themselves -- ARTIQ Python, processed by the ARTIQ compiler and loaded from the host machine -- rest on top of and are framed and supported by the firmware, in the same sense way that application software on your PC rests on top of an operating system. All together, software kernels communicate with the firmware to set parameters for the gateware, which passes signals directly to the hardware.

These frameworks are built to be self-contained and extensible. To make additions to the gateware, for example, we do not necessarily need to make changes to the firmware; we can interact purely with the interfaces provided on either side.

Extending gateware logic
------------------------

As briefly explained in :doc:`rtio`, when we talk about RTIO infrastructure, we are primarily speaking of structures implemented in gateware. The FIFO banks which hold scheduled output events or recorded input events, for example, are in gateware. Sequence errors, overflow exceptions, event spreading, and so on, happen in the gateware. In some cases, you may want to make relatively simple, parametric changes to existing RTIO, like changing the sizes of certain queues. In this case, it can be as simple as tracking down the part of the code where this parameter is set, changing it, and :doc:`rebuilding the binaries <building_developing>`.

.. warning::
    Note that FPGA resources are finite, and buffer sizes, lane counts, etc., are generally chosen to maximize available resources already, with different values depending on the core device in use. Blanket increases will likely quickly outstrip the capacity of your FPGA and fail to build. Increasing the depth of a particular channel you know to be heavily used is more likely to succeed; the easiest way to find out is to attempt the build and observe what results.

Gateware in ARTIQ is housed in ``artiq/gateware`` on the main ARTIQ repository and (for Zynq-specific additions) in ``artiq-zynq/src/gateware`` on ARTIQ-Zynq. The starting point for figuring out your changes will often be the *target file*, which is core device-specific and which you may recognize as the primary module called when building gateware. Depending on your core device, simply track down the file named after it, as in ``kasli.py``, ``kasli_soc.py``, and so on. Note that the Kasli and Kasli-SoC targets are designed to take JSON description files as input, whereas their KC705 and ZC706 equivalents work with hardcoded variants instead.

To change parameters related to particular peripherals, see also the files ``eem.py`` and ``eem_7series.py``, which describe the core device's interface with other EEM cards in Migen terms, and contain ``add_std`` methods that in turn reference specific gateware modules and assign RTIO channels.

Adding a module to gateware
^^^^^^^^^^^^^^^^^^^^^^^^^^^

To demonstrate how RTIO can be *extended,* on the other hand, we will develop a new interface entirely for the control of certain hardware -- in our case, for a simple example, the core device LEDs. If you haven't already, follow the instructions in :doc:`building_developing` to clone the ARTIQ repository and set up a development environment. The first part of our addition will be a module added to ``gateware/rtio/phy`` (PHY, for interaction with the physical layer), written in the Migen Fragmented Hardware Description Language (FHDL).

.. seealso::
    To find reference material for FHDL and the Migen constructs we will use, see the Migen manual, in particular the page `The FHDL domain-specific language <https://m-labs.hk/migen/manual/fhdl.html>`_.

.. warning::
    If you have never worked with a hardware description language before, it is important to understand that hardware description is fundamentally different to programming in a language like Python or Rust. At its most basic, a program is a set of instructions: a step-by-step guide to a task you want to see performed, where each step is written, and executed, principally in sequence. In contrast, hardware description is *a description*. It specifies the static state of a piece of hardware. There are no 'steps', and no chronological execution, only stated facts about how the system should be built.

    The examples we will handle in this tutorial are simple, and Migen makes for a much more manageable syntax than traditional languages like VHDL and Verilog, but keep in mind that we are describing how a system connects and interlocks its signals, *not* operations it should perform.

Normally, the PHY module used for LEDs is the ``Output`` of ``ttl_simple.py``. Take a look at its source code. Note that values like ``override`` and ``probes`` exist to support RTIO MonInj -- ``probes`` for monitoring, ``override`` for injection -- and are not involved with normal control of the output. Note also that ``pad``, among  engineers, refers to an input/output pad, i.e. a physical connection through which signals are sent. ``pad_n`` is its negative pair, necessary only for certain kinds of TTLs and not applicable to LEDs.

Interface and signals
"""""""""""""""""""""

To get started, create a new file in ``gateware/rtio/phy``. Call it ``linked_leds.py``. In it, create a class ``Output``, which will inherit from Migen's ``Module``, and give it an ``init`` method, which takes two pads as input: ::

    from migen import *

    class Output(Module):

        def __init__(self, pad0, pad1):

``pad0`` and ``pad1`` will represent output pads, in our case ultimately connecting to the board's user LEDs. On the other side, to receive output events from a RTIO FIFO queue, we will use an ``Interface`` provided by the ``rtlink`` module, also found in ``artiq/gateware``. Both output and input interfaces are available, and both can be combined into one link, but we are only handling output events. We use the ``data_width`` parameter to request an interface that is 2 bits wide: ::

    from migen import *
    from artiq.gateware.rtio import rtlink

    class Output(Module):

        def __init__(self, pad0, pad1):
            self.rtlink = rtlink.Interface(rtlink.OInterface(2))

In our example, rather than controlling both LEDs manually using ``on`` and ``off``, which is the functionality ``ttl_simple.py`` provides, we will control one LED manually and have the gateware determine the value of the other based on the first. This same logic would be easy (in fact, much easier) to implement in ARTIQ Python; the advantage of placing it in gateware is that logic in gateware is *extremely fast,* in effect 'instant', i.e., completed within a single clock cycle. Rather than waiting for a CPU to process and respond to instructions, a response can happen at the speed of electronics.

.. note::
    The truth is naturally more complicated, and it depends how complex the logic in question is. An overlong chain of gateware logic will fail to settle within a single RTIO clock cycle, causing a wide array of potential problems that are difficult to diagnose and difficult to fix; the only solutions are to simplify the logic, deliberately split it across multiple clock cycles (correspondingly increasing latency), or to decrease the speed of the clock (increasing latency for *everything* the device does).

    Suffice to say that you are unlikely to encounter timing failures with the kind of simple logic demonstrated in this tutorial, and that designing gateware logic to run in as few cycles as possible without 'failing timing' is an engineering discipline in itself, and indeed much of what FPGA developers spend their time on.

In practice, of course, since ARTIQ explicitly allows scheduling simultaneous output events to different channels, there's still no reason to make gateware modifications to accomplish this. After all, leveraging the real-time capabilities of customized gateware without making it necessary to *write* it is much of the point of ARTIQ as a system. Only in more complex cases, such as directly binding inputs to outputs without feeding back through the CPU, might gateware-level additions become necessary.

For now, add two intermediate signals for our logic, instances of the Migen ``Signal`` construct: ::

    def __init__(self, pad0, pad1):
        self.rtlink = rtlink.Interface(rtlink.OInterface(2))
        sync = Signal()
        pad0_o = Signal()

.. note::
    Note that a gateware 'signal' is not a signal in the sense of being a piece of transmitted information. Rather, it represents a channel, which bits of information can be held in. To conceptualize a Migen ``Signal``, take it as a kind of register: a box that holds a certain number of bits, and can update those bits from an input, or broadcast them to an output connection. The number of bits is arbitrary, e.g., a ``Signal(2)`` will be two bits wide, but in our example we handle only single-bit registers.

These are our inputs, outputs, and intermediate signals. By convention, in Migen, these definitions are all made at the beginning of a module, and separated from the logic that interconnects them with a line containing the three symbols ``###``. See also ``ttl_simple.py`` and other modules.

Since hardware description is not linear or chronological, nothing strictly prevents us from making these statements in any other order -- in fact, except for syntax, nothing particularly prevents us from defining the connections between the signals before we define the signals themselves -- but for readable and maintainable code, this format is vastly preferrable.

Combinatorial and synchronous statements
""""""""""""""""""""""""""""""""""""""""

After the ``###`` separator, we will set the connecting logic. A Migen ``Module`` has several special attributes, to which different logical statements can be assigned. We will be using ``self.sync``, for synchronous statements, and ``self.comb``, for combinatorial statements. If a statement is *synchronous*, it is only updated once per clock cycle, i.e. at the next tick of the clock. If a statement is *combinatorial*, it is updated whenever one of its inputs change, i.e. 'instantly'.

Add a synchronous block as follows: ::

    self.sync.rio_phy += [
        If(self.rtlink.o.stb,
            pad0_o.eq(self.rtlink.o.data[0] ^ pad0_o),
            sync.eq(self.rtlink.o.data[1])
        )
    ]

In other words, at every tick of the ``rtio_phy`` clock, if the ``rtlink`` strobe signal (which is set to high when the data is valid, i.e., when an output event has just reached the PHY) is high, the ``pad0_o`` and ``sync`` registers are updated according to the input data on ``rtlink``.

``sync`` is simply set equal to the incoming bit. ``pad0_o``, on the other hand, flips its old value if the input is ``1``, and keeps it if the input is ``0``. Note that ``^``, which you may know as the Python notation for a bitwise XOR operation, here simply represents a XOR gate. In summary, we can flip the value of ``pad0`` with the first bit of the interface, and set the value of ``sync`` with the other.

Add the combinatorial block as follows: ::

    self.comb += [
        pad0.eq(pad0_o),
        If(sync,
            pad1.eq(pad0_k)
        )
    ]

The output ``pad0`` is continuously connected to the value of the ``pad0_o`` register. The output of ``pad1`` is set equal to that of ``pad0``, but only if the ``sync`` register is high, or ``1``.

The module is now capable of accepting RTIO output events and applying them to the hardware outputs. What we can't yet do is generate these output events in an ARTIQ kernel. To do that, we need to a core device driver.

Adding a core device driver
^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you have been writing ARTIQ experiments for any length of time, you will already be familiar with the core device drivers. Their reference is kept in this manual on the page :doc:`core_drivers_reference`; their methods are commonly used to manipulate the core device and its close peripherals.

Source code for these drivers is kept in the directory ``artiq/coredevice``. Create a new file, again called ``linked_led.py``, in this directory.

The drivers are software, not gateware, and they are written in regular ARTIQ Python. They use methods given in ``coredevice/rtio.py`` to queue input and output events to RTIO channels. We will start with its ``__init__``, the method ``get_rtio_channels`` (which is formulaic, and exists only to be used by :meth:`~artiq.frontend.artiq_rtiomap`), and a output set method ``set_o``: ::

    from artiq.language.core import *
    from artiq.language.types import *
    from artiq.coredevice.rtio import rtio_output

    class LinkedLED:

        def __init__(self, dmgr, channel, core_device="core"):
            self.core = dmgr.get(core_device)
            self.channel = channel
            self.target_o = channel << 8

        @staticmethod
        def get_rtio_channels(channel, **kwargs):
            return [(channel, None)]

        @kernel
        def set_o(self, o):
            rtio_output(self.target_o, o)

Now we can write the kernel API. In the gateware, bit 0 flips the value of the first pad: ::

        @kernel
        def flip_led(self):
            self.set_o(0b01)

and bit 1 synchronizes the second pad to the first: ::

        @kernel
        def set_sync(self):
            self.set_o(0b10)

There's no reason we can't do both at the same time: ::

        @kernel
        def flip_and_sync(self):
            self.set_o(0b11)

Target and device database
^^^^^^^^^^^^^^^^^^^^^^^^^^

Our ``linked_led`` PHY module exists, but in order for it to be generated as part of a set of ARTIQ binaries, we need to add it to one of the target files. Find the target file for your core device, as described above. Each target file is structured differently; track down the part of the file where channels and PHY modules are assigned to the user LEDs. Depending on your core device, there may be two or more LEDs that are available. Look for lines similar to: ::

    for i in (0, 1):
        user_led = self.platform.request("user_led", i)
        phy = ttl_simple.Output(user_led)
        self.submodules += phy
        self.rtio_channels.append(rtio.Channel.from_phy(phy))

Edit the code so that, rather than assigning a separate PHY and channel to each LED, two of the LEDs are grouped together in ``linked_led``. You might use something like: ::

    phy = linked_led.Output(self.platform.request("user_led", 0), self.platform.request("user_led", 1))
    self.submodules += phy
    self.rtio_channels.append(rtio.Channel.from_phy(phy))

Save the target file, under a different name if you prefer. Follow the instructions in :doc:`building_developing` to build the gateware, being sure to use your edited target file for the gateware, and flash your core device, for simplicity preferably a standalone configuration without peripherals.

Correspondingly, before you can access your new core device driver from a kernel, it must be added to your device database. Find your ``device_db.py``. Delete the entries dedicated to the user LEDs that you have repurposed; if you tried to control those LEDs using the standard TTL interfaces now, the corresponding gateware would be missing anyway. Add an entry with your new driver, as in: ::

    device_db["leds"] = {
        "type": "local",
        "module": "artiq.coredevice.linked_led",
        "class": "LinkedLED",
        "arguments": {"channel": 0x000008}
    }

.. warning::
    Channel numbers are assigned sequentially in each time ``rtio_channels.append()`` is called. Since we assigned the channel for our linked LEDs in the same location as the old user LEDs, we can trust that the correct channel number will be that previously used for the first LED -- check the unedited device database first to make certain.

    Depending on how your device database was written, note that the channel numbers for other peripherals, if they are present, *will have changed*, and :meth:`~artiq.frontend.artiq_ddb_template` will not generate their numbers correctly unless it is edited to match the new assignments of the user LEDs. For a longer-term gateware change, especially the addition of a new EEM card, ``artiq/frontend/artiq_ddb_template.py`` and ``artiq/coredevice/coredevice_generic.schema`` should be edited accordingly, so that system descriptions and device databases can continue to be parsed and generated correctly.

Test experiments
^^^^^^^^^^^^^^^^

Now the device ``leds`` can be called from your device database, and its corresponding driver accessed, just as with any other device. Try writing some miniature experiments, for instance ``flip.py``: ::

    from artiq.experiment import *

    class flip(EnvExperiment):
        def build(self):
            self.setattr_device("core")
            self.setattr_device("leds")

        @kernel
        def run(self):
            self.core.reset()
            self.leds.flip_led()

and ``sync.py``: ::

    from artiq.experiment import *

    class sync(EnvExperiment):
        def build(self):
            self.setattr_device("core")
            self.setattr_device("leds")

        @kernel
        def run(self):
            self.core.reset()
            self.leds.set_sync()

Run these and observe the results. Congratulations! You have successfully constructed an extension to the ARTIQ RTIO.

.. + 'Adding custom EEMs' and 'Merging support'