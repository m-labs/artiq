from artiq.language.core import *
from artiq.language.types import *
from artiq.language.units import *
from artiq.coredevice.rtio import rtio_output
from artiq.coredevice.exceptions import DDSError

from numpy import int32, int64


_PHASE_MODE_DEFAULT   = -1
PHASE_MODE_CONTINUOUS = 0
PHASE_MODE_ABSOLUTE   = 1
PHASE_MODE_TRACKING   = 2


class DDSParams:
    def __init__(self):
        self.bus_channel = 0
        self.channel     = 0
        self.ftw         = 0
        self.pow         = 0
        self.phase_mode  = 0
        self.amplitude   = 0


class BatchContextManager:
    kernel_invariants = {"core", "core_dds", "params"}

    def __init__(self, core_dds):
        self.core_dds = core_dds
        self.core     = self.core_dds.core
        self.active   = False
        self.params   = [DDSParams() for _ in range(16)]
        self.count    = 0
        self.ref_time = int64(0)

    @kernel
    def __enter__(self):
        """Starts a DDS command batch. All DDS commands are buffered
        after this call, until ``batch_exit`` is called.

        The time of execution of the DDS commands is the time cursor position
        when the batch is entered."""
        if self.active:
            raise DDSError("DDS batch entered twice")

        self.active   = True
        self.count    = 0
        self.ref_time = now_mu()

    @kernel
    def append(self, bus_channel, channel, ftw, pow, phase_mode, amplitude):
        if self.count == len(self.params):
            raise DDSError("Too many commands in DDS batch")

        params = self.params[self.count]
        params.bus_channel = bus_channel
        params.channel     = channel
        params.ftw         = ftw
        params.pow         = pow
        params.phase_mode  = phase_mode
        params.amplitude   = amplitude
        self.count += 1

    @kernel
    def __exit__(self, type, value, traceback):
        """Ends a DDS command batch. All buffered DDS commands are issued
        on the bus."""
        if not self.active:
            raise DDSError("DDS batch exited twice")

        self.active = False
        at_mu(self.ref_time - self.core_dds.batch_duration_mu())
        for i in range(self.count):
            param = self.params[i]
            self.core_dds.program(self.ref_time,
                                  param.bus_channel, param.channel, param.ftw,
                                  param.pow, param.phase_mode, param.amplitude)


class DDSGroup:
    """Core device Direct Digital Synthesis (DDS) driver.

    Gives access to the DDS functionality of the core device.

    :param sysclk: DDS system frequency. The DDS system clock must be a
        phase-locked multiple of the RTIO clock.
    """

    kernel_invariants = {"core", "sysclk", "batch"}

    def __init__(self, dmgr, sysclk, core_device="core"):
        self.core   = dmgr.get(core_device)
        self.sysclk = sysclk
        self.batch  = BatchContextManager(self)

    @kernel
    def batch_duration_mu(self):
        raise NotImplementedError

    @kernel
    def init(self, bus_channel, channel):
        raise NotImplementedError

    @kernel
    def program(self, ref_time, bus_channel, channel, ftw, pow, phase_mode, amplitude):
        raise NotImplementedError

    @kernel
    def set(self, bus_channel, channel, ftw, pow, phase_mode, amplitude):
        if self.batch.active:
            self.batch.append(bus_channel, channel, ftw, pow, phase_mode, amplitude)
        else:
            ref_time = now_mu()
            at_mu(ref_time - self.program_duration_mu)
            self.program(ref_time,
                         bus_channel, channel, ftw, pow, phase_mode, amplitude)

    @portable(flags={"fast-math"})
    def frequency_to_ftw(self, frequency):
        """Returns the frequency tuning word corresponding to the given
        frequency.
        """
        return round(float(int64(2)**32*frequency/self.sysclk))

    @portable(flags={"fast-math"})
    def ftw_to_frequency(self, ftw):
        """Returns the frequency corresponding to the given frequency tuning
        word.
        """
        return ftw*self.sysclk/int64(2)**32

    @portable(flags={"fast-math"})
    def turns_to_pow(self, turns):
        """Returns the phase offset word corresponding to the given phase
        in turns."""
        return round(float(turns*2**self.pow_width))

    @portable(flags={"fast-math"})
    def pow_to_turns(self, pow):
        """Returns the phase in turns corresponding to the given phase offset
        word."""
        return pow/2**self.pow_width

    @portable(flags={"fast-math"})
    def amplitude_to_asf(self, amplitude):
        """Returns amplitude scale factor corresponding to given amplitude."""
        return round(float(amplitude*0x0fff))

    @portable(flags={"fast-math"})
    def asf_to_amplitude(self, asf):
        """Returns the amplitude corresponding to the given amplitude scale
           factor."""
        return asf/0x0fff


class DDSChannel:
    """Core device Direct Digital Synthesis (DDS) channel driver.

    Controls one DDS channel managed directly by the core device's runtime.

    This class should not be used directly, instead, use the chip-specific
    drivers such as ``DDSChannelAD9914``.

    The time cursor is not modified by any function in this class.

    :param bus: name of the DDS bus device that this DDS is connected to.
    :param channel: channel number of the DDS device to control.
    """

    kernel_invariants = {
        "core", "core_dds", "bus_channel", "channel",
    }

    def __init__(self, dmgr, bus_channel, channel, core_dds_device="core_dds"):
        self.core_dds    = dmgr.get(core_dds_device)
        self.core        = self.core_dds.core
        self.bus_channel = bus_channel
        self.channel     = channel
        self.phase_mode  = PHASE_MODE_CONTINUOUS

    @kernel
    def init(self):
        """Resets and initializes the DDS channel.

        This needs to be done for each DDS channel before it can be used, and
        it is recommended to use the startup kernel for this.

        This function cannot be used in a batch; the correct way of
        initializing multiple DDS channels is to call this function
        sequentially with a delay between the calls. 2ms provides a good
        timing margin."""
        self.core_dds.init(self.bus_channel, self.channel)

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

        The "frequency update" pulse is sent to the DDS with a fixed latency
        with respect to the current position of the time cursor.

        :param frequency: frequency to generate.
        :param phase: adds an offset, in turns, to the phase.
        :param phase_mode: if specified, overrides the default phase mode set
            by ``set_phase_mode`` for this call.
        """
        if phase_mode == _PHASE_MODE_DEFAULT:
            phase_mode = self.phase_mode
        self.core_dds.set(self.bus_channel, self.channel, frequency, phase, phase_mode, amplitude)

    @kernel
    def set(self, frequency, phase=0.0, phase_mode=_PHASE_MODE_DEFAULT,
            amplitude=1.0):
        """Like ``set_mu``, but uses Hz and turns."""
        self.set_mu(self.core_dds.frequency_to_ftw(frequency),
                    self.core_dds.turns_to_pow(phase), phase_mode,
                    self.core_dds.amplitude_to_asf(amplitude))


AD9914_REG_CFR1L = 0x01
AD9914_REG_CFR1H = 0x03
AD9914_REG_CFR2L = 0x05
AD9914_REG_CFR2H = 0x07
AD9914_REG_CFR3L = 0x09
AD9914_REG_CFR3H = 0x0b
AD9914_REG_CFR4L = 0x0d
AD9914_REG_CFR4H = 0x0f
AD9914_REG_FTWL  = 0x2d
AD9914_REG_FTWH  = 0x2f
AD9914_REG_POW   = 0x31
AD9914_REG_ASF   = 0x33
AD9914_REG_USR0  = 0x6d
AD9914_FUD       = 0x80
AD9914_GPIO      = 0x81


class DDSGroupAD9914(DDSGroup):
    """Driver for AD9914 DDS chips. See ``DDSGroup`` for a description
    of the functionality."""
    kernel_invariants = DDSGroup.kernel_invariants.union({
        "pow_width", "rtio_period_mu", "sysclk_per_mu", "write_duration_mu", "dac_cal_duration_mu",
        "init_duration_mu", "init_sync_duration_mu", "program_duration_mu",
        "first_dds_bus_channel", "dds_channel_count", "continuous_phase_comp"
    })

    pow_width = 16

    def __init__(self, *args, first_dds_bus_channel, dds_bus_count, dds_channel_count, **kwargs):
        super().__init__(*args, **kwargs)

        self.first_dds_bus_channel = first_dds_bus_channel
        self.dds_bus_count         = dds_bus_count
        self.dds_channel_count     = dds_channel_count

        self.rtio_period_mu        = int64(8)
        self.sysclk_per_mu         = int32(self.sysclk * self.core.ref_period)

        self.write_duration_mu     = 5 * self.rtio_period_mu
        self.dac_cal_duration_mu   = 147000 * self.rtio_period_mu
        self.init_duration_mu      = 8 * self.write_duration_mu + self.dac_cal_duration_mu
        self.init_sync_duration_mu = 16 * self.write_duration_mu + 2 * self.dac_cal_duration_mu
        self.program_duration_mu   = 6 * self.write_duration_mu

        self.continuous_phase_comp = [0] * (self.dds_bus_count * self.dds_channel_count)

    @kernel
    def batch_duration_mu(self):
        return self.batch.count * (self.program_duration_mu +
                                   self.write_duration_mu) # + FUD time

    @kernel
    def write(self, bus_channel, addr, data):
        rtio_output(now_mu(), bus_channel, addr, data)
        delay_mu(self.write_duration_mu)

    @kernel
    def init(self, bus_channel, channel):
        delay_mu(-self.init_duration_mu)
        self.write(bus_channel, AD9914_GPIO,      (1 << channel) << 1);

        self.write(bus_channel, AD9914_REG_CFR1H, 0x0000) # Enable cosine output
        self.write(bus_channel, AD9914_REG_CFR2L, 0x8900) # Enable matched latency
        self.write(bus_channel, AD9914_REG_CFR2H, 0x0080) # Enable profile mode
        self.write(bus_channel, AD9914_REG_ASF,   0x0fff) # Set amplitude to maximum
        self.write(bus_channel, AD9914_REG_CFR4H, 0x0105) # Enable DAC calibration
        self.write(bus_channel, AD9914_FUD,       0)
        delay_mu(self.dac_cal_duration_mu)
        self.write(bus_channel, AD9914_REG_CFR4H, 0x0005) # Disable DAC calibration
        self.write(bus_channel, AD9914_FUD,       0)

    @kernel
    def init_sync(self, bus_channel, channel, sync_delay):
        delay_mu(-self.init_sync_duration_mu)
        self.write(bus_channel, AD9914_GPIO,      (1 << channel) << 1)

        self.write(bus_channel, AD9914_REG_CFR4H, 0x0105) # Enable DAC calibration
        self.write(bus_channel, AD9914_FUD,       0)
        delay_mu(self.dac_cal_duration_mu)
        self.write(bus_channel, AD9914_REG_CFR4H, 0x0005) # Disable DAC calibration
        self.write(bus_channel, AD9914_FUD,       0)
        self.write(bus_channel, AD9914_REG_CFR2L, 0x8b00) # Enable matched latency and sync_out
        self.write(bus_channel, AD9914_FUD,       0)
        # Set cal with sync and set sync_out and sync_in delay
        self.write(bus_channel, AD9914_REG_USR0,  0x0840 | (sync_delay & 0x3f))
        self.write(bus_channel, AD9914_FUD,       0)
        self.write(bus_channel, AD9914_REG_CFR4H, 0x0105) # Enable DAC calibration
        self.write(bus_channel, AD9914_FUD,       0)
        delay_mu(self.dac_cal_duration_mu)
        self.write(bus_channel, AD9914_REG_CFR4H, 0x0005) # Disable DAC calibration
        self.write(bus_channel, AD9914_FUD,       0)
        self.write(bus_channel, AD9914_REG_CFR1H, 0x0000) # Enable cosine output
        self.write(bus_channel, AD9914_REG_CFR2H, 0x0080) # Enable profile mode
        self.write(bus_channel, AD9914_REG_ASF,   0x0fff) # Set amplitude to maximum
        self.write(bus_channel, AD9914_FUD,       0)

    @kernel
    def program(self, ref_time, bus_channel, channel, ftw, pow, phase_mode, amplitude):
        self.write(bus_channel, AD9914_GPIO,      (1 << channel) << 1)

        self.write(bus_channel, AD9914_REG_FTWL,  ftw & 0xffff)
        self.write(bus_channel, AD9914_REG_FTWH,  (ftw >> 16) & 0xffff)

        # We need the RTIO fine timestamp clock to be phase-locked
        # to DDS SYSCLK, and divided by an integer self.sysclk_per_mu.
        dds_bus_index = bus_channel - self.first_dds_bus_channel
        phase_comp_index = dds_bus_index * self.dds_channel_count + channel
        if phase_mode == PHASE_MODE_CONTINUOUS:
            # Do not clear phase accumulator on FUD
            # Disable autoclear phase accumulator and enables OSK.
            self.write(bus_channel, AD9914_REG_CFR1L, 0x0108)
            pow += self.continuous_phase_comp[phase_comp_index]
        else:
            # Clear phase accumulator on FUD
            # Enable autoclear phase accumulator and enables OSK.
            self.write(bus_channel, AD9914_REG_CFR1L, 0x2108)
            fud_time = now_mu() + 2 * self.write_duration_mu
            pow -= int32((ref_time - fud_time) * self.sysclk_per_mu * ftw >> (32 - self.pow_width))
            if phase_mode == PHASE_MODE_TRACKING:
                pow += int32(ref_time * self.sysclk_per_mu * ftw >> (32 - self.pow_width))
            self.continuous_phase_comp[phase_comp_index] = pow

        self.write(bus_channel, AD9914_REG_POW,  pow)
        self.write(bus_channel, AD9914_REG_ASF,  amplitude)
        self.write(bus_channel, AD9914_FUD,      0)


class DDSChannelAD9914(DDSChannel):
    """Driver for AD9914 DDS chips. See ``DDSChannel`` for a description
    of the functionality."""
    @kernel
    def init_sync(self, sync_delay=0):
        """Resets and initializes the DDS channel as well as configures
        the AD9914 DDS for synchronisation. The synchronisation procedure
        follows the steps outlined in the AN-1254 application note.

        This needs to be done for each DDS channel before it can be used, and
        it is recommended to use the startup kernel for this.

        This function cannot be used in a batch; the correct way of
        initializing multiple DDS channels is to call this function
        sequentially with a delay between the calls. 10ms provides a good
        timing margin.

        :param sync_delay: integer from 0 to 0x3f that sets the value of
            SYNC_OUT (bits 3-5) and SYNC_IN (bits 0-2) delay ADJ bits.
        """
        self.core_dds.init_sync(self.bus_channel, self.channel, sync_delay)
