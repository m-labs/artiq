from artiq.language.core import *
from artiq.language.units import *


_PHASE_MODE_DEFAULT = -1
# keep in sync with dds.h
PHASE_MODE_CONTINUOUS = 0
PHASE_MODE_ABSOLUTE = 1
PHASE_MODE_TRACKING = 2


class _BatchContextManager:
    def __init__(self, dds_bus):
        self.dds_bus = dds_bus

    @kernel
    def __enter__(self):
        self.dds_bus.batch_enter()

    @kernel
    def __exit__(self, type, value, traceback):
        self.dds_bus.batch_exit()


class DDSBus:
    """Core device Direct Digital Synthesis (DDS) bus batching driver.

    Manages batching of DDS commands on a DDS shared bus."""
    def __init__(self, dmgr):
        self.core = dmgr.get("core")
        self.batch = _BatchContextManager(self)

    @kernel
    def batch_enter(self):
        """Starts a DDS command batch. All DDS commands are buffered
        after this call, until ``batch_exit`` is called."""
        syscall("dds_batch_enter", now_mu())

    @kernel
    def batch_exit(self):
        """Ends a DDS command batch. All buffered DDS commands are issued
        on the bus, and FUD is pulsed at the time the batch started."""
        syscall("dds_batch_exit")


class _DDSGeneric:
    """Core device Direct Digital Synthesis (DDS) driver.

    Controls one DDS channel managed directly by the core device's runtime.

    This class should not be used directly, instead, use the chip-specific
    drivers such as ``AD9858`` and ``AD9914``.

    :param sysclk: DDS system frequency.
    :param channel: channel number of the DDS device to control.
    """
    def __init__(self, dmgr, sysclk, channel):
        self.core = dmgr.get("core")
        self.sysclk = sysclk
        self.channel = channel
        self.phase_mode = PHASE_MODE_CONTINUOUS

    @portable
    def frequency_to_ftw(self, frequency):
        """Returns the frequency tuning word corresponding to the given
        frequency.
        """
        return round(2**32*frequency/self.sysclk)

    @portable
    def ftw_to_frequency(self, ftw):
        """Returns the frequency corresponding to the given frequency tuning
        word.
        """
        return ftw*self.sysclk/2**32

    @portable
    def turns_to_pow(self, turns):
        """Returns the phase offset word corresponding to the given phase
        in turns."""
        return round(turns*2**self.pow_width)

    @portable
    def pow_to_turns(self, pow):
        """Returns the phase in turns corresponding to the given phase offset
        word."""
        return pow/2**self.pow_width

    @kernel
    def init(self):
        """Resets and initializes the DDS channel.

        The runtime does this for all channels upon core device startup."""
        syscall("dds_init", now_mu(), self.channel)

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
    def set_mu(self, frequency, phase=0, phase_mode=_PHASE_MODE_DEFAULT):
        """Sets the DDS channel to the specified frequency and phase.

        This uses machine units (FTW and POW). The frequency tuning word width
        is 32, whereas the phase offset word width depends on the type of DDS
        chip and can be retrieved via the ``pow_width`` attribute.

        :param frequency: frequency to generate.
        :param phase: adds an offset, in turns, to the phase.
        :param phase_mode: if specified, overrides the default phase mode set
            by ``set_phase_mode`` for this call.
        """
        if phase_mode == _PHASE_MODE_DEFAULT:
            phase_mode = self.phase_mode
        syscall("dds_set", now_mu(), self.channel,
           frequency, round(phase*2**self.pow_width), phase_mode)

    @kernel
    def set(self, frequency, phase=0, phase_mode=_PHASE_MODE_DEFAULT):
        """Like ``set_mu``, but uses Hz and turns."""
        self.set_mu(self.frequency_to_ftw(frequency),
                    self.turns_to_pow(phase), phase_mode)


class AD9858(_DDSGeneric):
    """Driver for AD9858 DDS chips. See ``_DDSGeneric`` for a description
    of the functionality."""
    pow_width = 14


class AD9914(_DDSGeneric):
    """Driver for AD9914 DDS chips. See ``_DDSGeneric`` for a description
    of the functionality."""
    pow_width = 16
