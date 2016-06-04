from artiq.language.core import *
from artiq.language.types import *
from artiq.language.units import *


_PHASE_MODE_DEFAULT = -1
# keep in sync with dds.h
PHASE_MODE_CONTINUOUS = 0
PHASE_MODE_ABSOLUTE = 1
PHASE_MODE_TRACKING = 2


@syscall(flags={"nowrite"})
def dds_init(time_mu: TInt64, bus_channel: TInt32, channel: TInt32) -> TNone:
    raise NotImplementedError("syscall not simulated")

@syscall(flags={"nowrite"})
def dds_set(time_mu: TInt64, bus_channel: TInt32, channel: TInt32, ftw: TInt32,
            pow: TInt32, phase_mode: TInt32, amplitude: TInt32) -> TNone:
    raise NotImplementedError("syscall not simulated")

@syscall(flags={"nowrite"})
def dds_batch_enter(time_mu: TInt64) -> TNone:
    raise NotImplementedError("syscall not simulated")

@syscall(flags={"nowrite"})
def dds_batch_exit() -> TNone:
    raise NotImplementedError("syscall not simulated")


class _BatchContextManager:
    kernel_invariants = {"core", "core_dds"}

    def __init__(self, core_dds):
        self.core_dds = core_dds
        self.core = self.core_dds.core

    @kernel
    def __enter__(self):
        self.core_dds.dds_batch_enter()

    @kernel
    def __exit__(self, type, value, traceback):
        self.core_dds.dds_batch_exit()


class CoreDDS:
    """Core device Direct Digital Synthesis (DDS) driver.

    Gives access to the DDS functionality of the core device.

    :param sysclk: DDS system frequency. The DDS system clock must be a
        phase-locked multiple of the RTIO clock.
    """

    kernel_invariants = {"core", "sysclk", "batch"}

    def __init__(self, dmgr, sysclk, core_device="core"):
        self.core = dmgr.get(core_device)
        self.sysclk = sysclk
        self.batch = _BatchContextManager(self)

    @kernel
    def dds_batch_enter(self):
        """Starts a DDS command batch. All DDS commands are buffered
        after this call, until ``batch_exit`` is called.

        The time of execution of the DDS commands is the time of entering the
        batch (as closely as hardware permits)."""
        dds_batch_enter(now_mu())

    @kernel
    def dds_batch_exit(self):
        """Ends a DDS command batch. All buffered DDS commands are issued
        on the bus."""
        dds_batch_exit()


class _DDSGeneric:
    """Core device Direct Digital Synthesis (DDS) channel driver.

    Controls one DDS channel managed directly by the core device's runtime.

    This class should not be used directly, instead, use the chip-specific
    drivers such as ``AD9858`` and ``AD9914``.

    :param bus: name of the DDS bus device that this DDS is connected to.
    :param channel: channel number of the DDS device to control.
    """

    kernel_invariants = {
        "core", "core_dds", "bus_channel", "channel", "pow_width"
    }

    def __init__(self, dmgr, bus_channel, channel, core_dds_device="core_dds"):
        self.core_dds = dmgr.get(core_dds_device)
        self.core = self.core_dds.core
        self.bus_channel = bus_channel
        self.channel = channel
        self.phase_mode = PHASE_MODE_CONTINUOUS

    @portable(flags=["fast-math"])
    def frequency_to_ftw(self, frequency):
        """Returns the frequency tuning word corresponding to the given
        frequency.
        """
        return round(int(2, width=64)**32*frequency/self.core_dds.sysclk)

    @portable(flags=["fast-math"])
    def ftw_to_frequency(self, ftw):
        """Returns the frequency corresponding to the given frequency tuning
        word.
        """
        return ftw*self.core_dds.sysclk/int(2, width=64)**32

    @portable(flags=["fast-math"])
    def turns_to_pow(self, turns):
        """Returns the phase offset word corresponding to the given phase
        in turns."""
        return round(turns*2**self.pow_width)

    @portable(flags=["fast-math"])
    def pow_to_turns(self, pow):
        """Returns the phase in turns corresponding to the given phase offset
        word."""
        return pow/2**self.pow_width

    @portable
    def amplitude_to_asf(self, amplitude):
        """Returns amplitude scale factor corresponding to given amplitude."""
        return round(amplitude*0x0fff)

    @portable
    def asf_to_amplitude(self, asf):
        """Returns the amplitude corresponding to the given amplitude scale
           factor."""
        return asf/0x0fff

    @kernel
    def init(self):
        """Resets and initializes the DDS channel.

        This needs to be done for each DDS channel before it can be used, and
        it is recommended to use the startup kernel for this.

        This function cannot be used in a batch; the correct way of
        initializing multiple DDS channels is to call this function
        sequentially with a delay between the calls. 2ms provides a good
        timing margin."""
        dds_init(now_mu(), self.bus_channel, self.channel)

    @kernel
    def set_phase_mode(self, phase_mode):
        """Sets the phase mode of the DDS channel. Supported phase modes are:

        * ``PHASE_MODE_CONTINUOUS``: the phase accumulator is unchanged when
          switching frequencies. The DDS phase is the sum of the phase
          accumulator and the phase offset. The only discrete jumps in the
          DDS output phase come from changes to the phase offset.

        * ``PHASE_MODE_ABSOLUTE``: the phase accumulator is reset when
          switching frequencies. Thus, the phase of the DDS at the time of
          the frequency change is equal to the phase offset.

        * ``PHASE_MODE_TRACKING``: when switching frequencies, the phase
          accumulator is set to the value it would have if the DDS had been
          running at the specified frequency since the start of the
          experiment.
        """
        self.phase_mode = phase_mode

    @kernel
    def set_mu(self, frequency, phase=0, phase_mode=_PHASE_MODE_DEFAULT,
               amplitude=0x0fff):
        """Sets the DDS channel to the specified frequency and phase.

        This uses machine units (FTW and POW). The frequency tuning word width
        is 32, whereas the phase offset word width depends on the type of DDS
        chip and can be retrieved via the ``pow_width`` attribute. The amplitude
        width is 12.

        :param frequency: frequency to generate.
        :param phase: adds an offset, in turns, to the phase.
        :param phase_mode: if specified, overrides the default phase mode set
            by ``set_phase_mode`` for this call.
        """
        if phase_mode == _PHASE_MODE_DEFAULT:
            phase_mode = self.phase_mode
        dds_set(now_mu(), self.bus_channel, self.channel,
                frequency, phase, phase_mode, amplitude)

    @kernel
    def set(self, frequency, phase=0.0, phase_mode=_PHASE_MODE_DEFAULT,
            amplitude=1.0):
        """Like ``set_mu``, but uses Hz and turns."""
        self.set_mu(self.frequency_to_ftw(frequency),
                    self.turns_to_pow(phase), phase_mode,
                    self.amplitude_to_asf(amplitude))


class AD9858(_DDSGeneric):
    """Driver for AD9858 DDS chips. See ``_DDSGeneric`` for a description
    of the functionality."""
    pow_width = 14


class AD9914(_DDSGeneric):
    """Driver for AD9914 DDS chips. See ``_DDSGeneric`` for a description
    of the functionality."""
    pow_width = 16
