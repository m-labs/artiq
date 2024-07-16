from numpy import int32, int64

from artiq.language.core import kernel, delay_mu, delay
from artiq.coredevice.rtio import rtio_output, rtio_input_data, rtio_input_timestamp
from artiq.language.units import us, ns, ms, MHz
from artiq.language.types import TInt32
from artiq.coredevice.dac34h84 import DAC34H84
from artiq.coredevice.trf372017 import TRF372017


PHASER_BOARD_ID = 19

PHASER_GW_BASE = 1
PHASER_GW_MIQRO = 2

PHASER_ADDR_BOARD_ID = 0x00
PHASER_ADDR_HW_REV = 0x01
PHASER_ADDR_GW_REV = 0x02
PHASER_ADDR_CFG = 0x03
PHASER_ADDR_STA = 0x04
PHASER_ADDR_CRC_ERR = 0x05
PHASER_ADDR_LED = 0x06
PHASER_ADDR_FAN = 0x07
PHASER_ADDR_DUC_STB = 0x08
PHASER_ADDR_ADC_CFG = 0x09
PHASER_ADDR_SPI_CFG = 0x0a
PHASER_ADDR_SPI_DIVLEN = 0x0b
PHASER_ADDR_SPI_SEL = 0x0c
PHASER_ADDR_SPI_DATW = 0x0d
PHASER_ADDR_SPI_DATR = 0x0e
PHASER_ADDR_SYNC_DLY = 0x0f

PHASER_ADDR_DUC0_CFG = 0x10
# PHASER_ADDR_DUC0_RESERVED0 = 0x11
PHASER_ADDR_DUC0_F = 0x12
PHASER_ADDR_DUC0_P = 0x16
PHASER_ADDR_DAC0_DATA = 0x18
PHASER_ADDR_DAC0_TEST = 0x1c

PHASER_ADDR_DUC1_CFG = 0x20
# PHASER_ADDR_DUC1_RESERVED0 = 0x21
PHASER_ADDR_DUC1_F = 0x22
PHASER_ADDR_DUC1_P = 0x26
PHASER_ADDR_DAC1_DATA = 0x28
PHASER_ADDR_DAC1_TEST = 0x2c

# servo registers
PHASER_ADDR_SERVO_CFG0 = 0x30
PHASER_ADDR_SERVO_CFG1 = 0x31

# 0x32 - 0x71 servo coefficients + offset data
PHASER_ADDR_SERVO_DATA_BASE = 0x32

# 0x72 - 0x78 Miqro channel profile/window memories
PHASER_ADDR_MIQRO_MEM_ADDR = 0x72
PHASER_ADDR_MIQRO_MEM_DATA = 0x74

# Miqro profile memory select
PHASER_MIQRO_SEL_PROFILE = 1 << 14

PHASER_SEL_DAC = 1 << 0
PHASER_SEL_TRF0 = 1 << 1
PHASER_SEL_TRF1 = 1 << 2
PHASER_SEL_ATT0 = 1 << 3
PHASER_SEL_ATT1 = 1 << 4

PHASER_STA_DAC_ALARM = 1 << 0
PHASER_STA_TRF0_LD = 1 << 1
PHASER_STA_TRF1_LD = 1 << 2
PHASER_STA_TERM0 = 1 << 3
PHASER_STA_TERM1 = 1 << 4
PHASER_STA_SPI_IDLE = 1 << 5

PHASER_DAC_SEL_DUC = 0
PHASER_DAC_SEL_TEST = 1

PHASER_HW_REV_VARIANT = 1 << 4

SERVO_COEFF_WIDTH = 16
SERVO_DATA_WIDTH = 16
SERVO_COEFF_SHIFT = 14
SERVO_T_CYCLE = (32+12+192+24+4)*ns  # Must match gateware ADC parameters


class Phaser:
    """Phaser 4-channel, 16-bit, 1 GS/s DAC coredevice driver.

    Phaser contains a 4-channel, 1 GS/s DAC chip with integrated upconversion,
    quadrature modulation compensation and interpolation features.

    The coredevice RTIO PHY and the Phaser gateware come in different modes
    that have different features. Phaser mode and coredevice PHY mode are both
    selected at their respective gateware compile-time and need to match.

    ===============  ==============  ===================================
    Phaser gateware  Coredevice PHY  Features per :class:`PhaserChannel`
    ===============  ==============  ===================================
    Base <= v0.5     Base            Base (5 :class:`PhaserOscillator`)
    Base >= v0.6     Base            Base + Servo
    Miqro >= v0.6    Miqro           :class:`Miqro`
    ===============  ==============  ===================================

    The coredevice driver (this class and :class:`PhaserChannel`) exposes
    the superset of all functionality regardless of the Coredevice RTIO PHY
    or Phaser gateware modes. This is to evade type unification limitations.
    Features absent in Coredevice PHY/Phaser gateware will not work and
    should not be accessed.

    **Base mode**

    The coredevice produces 2 IQ (in-phase and quadrature) data streams with 25
    MS/s and 14 bits per quadrature. Each data stream supports 5 independent
    numerically controlled IQ oscillators (NCOs, DDSs with 32-bit frequency, 
    16-bit phase, 15-bit amplitude, and phase accumulator clear functionality)
    added together. See :class:`PhaserChannel` and :class:`PhaserOscillator`.

    Together with a data clock, framing marker, a checksum and metadata for
    register access the streams are sent in groups of 8 samples over 1.5 Gb/s
    FastLink via a single EEM connector from coredevice to Phaser.

    On Phaser in the FPGA the data streams are buffered and interpolated
    from 25 MS/s to 500 MS/s 16-bit followed by a 500 MS/s digital upconverter
    with adjustable frequency and phase. The interpolation passband is 20 MHz
    wide, passband ripple is less than 1e-3 amplitude, stopband attenuation
    is better than 75 dB at offsets > 15 MHz and better than 90 dB at offsets
    > 30 MHz.

    The four 16-bit 500 MS/s DAC data streams are sent via a 32-bit parallel
    LVDS bus operating at 1 Gb/s per pin pair and processed in the DAC (Texas
    Instruments DAC34H84). On the DAC 2x interpolation, sinx/x compensation,
    quadrature modulator compensation, fine and coarse mixing as well as group
    delay capabilities are available. If desired, these features my be
    configured via the ``dac`` dictionary.

    The latency/group delay from the RTIO events setting
    :class:`PhaserOscillator` or :class:`PhaserChannel` DUC parameters all the
    way to the DAC outputs is deterministic. This enables deterministic
    absolute phase with respect to other RTIO input and output events
    (see :meth:`get_next_frame_mu()`).

    **Miqro mode**

    See :class:`Miqro`. Here the DAC operates in 4x interpolation.

    **Analog flow**

    The four analog DAC outputs are passed through anti-aliasing filters.

    In the baseband variant, the even/in-phase DAC channels feed 31.5 dB range
    attenuators and are available on the front panel. The odd outputs are
    available at MMCX connectors on board.

    In the upconverter variant, each IQ output pair feeds one quadrature
    upconverter (Texas Instruments TRF372017) with integrated PLL/VCO. This
    digitally configured analog quadrature upconverter supports offset tuning
    for carrier and sideband suppression. The output from the upconverter
    passes through the 31.5 dB range step attenuator and is available at the
    front panel.

    The DAC, the analog quadrature upconverters and the attenuators are
    configured through a shared SPI bus that is accessed and controlled via
    FPGA registers.

    **Servo**

    Each phaser output channel features a servo to control the RF output amplitude
    using feedback from an ADC. The servo consists of a first order IIR (infinite
    impulse response) filter fed by the ADC and a multiplier that scales the I
    and Q datastreams from the DUC by the IIR output. The IIR state is updated at
    the 3.788 MHz ADC sampling rate.

    Each channel IIR features 4 profiles, each consisting of the ``[b0, b1, a1]`` filter
    coefficients as well as an output offset. The coefficients and offset can be
    set for each profile individually and the profiles each have their own ``y0``,
    ``y1`` output registers (the ``x0``, ``x1`` inputs are shared). To avoid
    transient effects, care should be taken to not update the coefficents in the
    currently selected profile.

    The servo can be en- or disabled for each channel. When disabled, the servo
    output multiplier is simply bypassed and the datastream reaches the DAC unscaled.

    The IIR output can be put on hold for each channel. In hold mode, the filter
    still ingests samples and updates its input ``x0`` and ``x1`` registers, but
    does not update the ``y0``, ``y1`` output registers.

    After power-up the servo is disabled, in profile 0, with coefficients ``[0, 0, 0]``
    and hold is enabled. If older gateware without ther servo is loaded onto the
    Phaser FPGA, the device simply behaves as if the servo is disabled and none of
    the servo functions have any effect.

    .. note:: Various register settings of the DAC and the quadrature
        upconverters are available to be modified through the ``dac``, ``trf0``,
        ``trf1`` dictionaries. These can be set through the device database
        (``device_db.py``). The settings are frozen during instantiation of the
        class and applied during ``init()``. See the :class:`dac34H84` and
        :class:`trf372017` source for details.

    .. note:: To establish deterministic latency between RTIO time base and DAC
        output, the DAC FIFO read pointer value (``fifo_offset``) must be
        fixed. If `tune_fifo_offset` = ``True`` (the default) a value with maximum
        margin is determined automatically by `dac_tune_fifo_offset` each time
        :meth:`init` is called. This value should be used for the ``fifo_offset`` key
        of the ``dac`` settings of Phaser in ``device_db.py`` and automatic
        tuning should be disabled by `tune_fifo_offset` = ``False```.

    :param channel: Base RTIO channel number
    :param core_device: Core device name (default: "core")
    :param miso_delay: Fastlink MISO signal delay to account for cable
        and buffer round trip. Tuning this might be automated later.
    :param tune_fifo_offset: Tune the DAC FIFO read pointer offset
        (default=True)
    :param clk_sel: Select the external SMA clock input (1 or 0)
    :param sync_dly: SYNC delay with respect to ISTR.
    :param dac: DAC34H84 DAC settings as a dictionary.
    :param trf0: Channel 0 TRF372017 quadrature upconverter settings as a
        dictionary.
    :param trf1: Channel 1 TRF372017 quadrature upconverter settings as a
        dictionary.

    **Attributes:**

    * :attr:`channel`: List of two instances of :class:`PhaserChannel`
        To access oscillators, digital upconverters, PLL/VCO analog
        quadrature upconverters and attenuators.
    """
    kernel_invariants = {"core", "channel_base", "t_frame", "miso_delay",
                         "dac_mmap"}

    def __init__(self, dmgr, channel_base, miso_delay=1, tune_fifo_offset=True,
                 clk_sel=0, sync_dly=0, dac=None, trf0=None, trf1=None, gw_rev=PHASER_GW_BASE,
                 core_device="core"):
        self.channel_base = channel_base
        self.core = dmgr.get(core_device)
        # TODO: auto-align miso-delay in phy
        self.miso_delay = miso_delay
        # frame duration in mu (10 words, 8 clock cycles each 4 ns)
        # self.core.seconds_to_mu(10*8*4*ns)  # unfortunately this returns 319
        assert self.core.ref_period == 1*ns
        self.t_frame = 10*8*4
        self.frame_tstamp = int64(0)
        self.clk_sel = clk_sel
        self.tune_fifo_offset = tune_fifo_offset
        self.sync_dly = sync_dly
        self.gw_rev = gw_rev  # verified in init()

        self.dac_mmap = DAC34H84(dac).get_mmap()

        self.channel = [PhaserChannel(self, ch, trf)
                        for ch, trf in enumerate([trf0, trf1])]

    @staticmethod
    def get_rtio_channels(channel_base, gw_rev=PHASER_GW_BASE, **kwargs):
        if gw_rev == PHASER_GW_MIQRO:
            return [(channel_base, "base"), (channel_base + 1, "ch0"), (channel_base + 2, "ch1")]
        elif gw_rev == PHASER_GW_BASE:
            return [(channel_base, "base"),
                    (channel_base + 1, "ch0 frequency"),
                    (channel_base + 2, "ch0 phase amplitude"),
                    (channel_base + 3, "ch1 frequency"),
                    (channel_base + 4, "ch1 phase amplitude")]
        raise ValueError("invalid gw_rev `{}`".format(gw_rev))

    @kernel
    def init(self, debug=False):
        """Initialize the board.

        Verifies board and chip presence, resets components, performs
        communication and configuration tests and establishes initial
        conditions.
        """
        board_id = self.read8(PHASER_ADDR_BOARD_ID)
        if board_id != PHASER_BOARD_ID:
            raise ValueError("invalid board id")
        delay(.1*ms)  # slack

        hw_rev = self.read8(PHASER_ADDR_HW_REV)
        delay(.1*ms)  # slack
        is_baseband = hw_rev & PHASER_HW_REV_VARIANT

        gw_rev = self.read8(PHASER_ADDR_GW_REV)
        if debug:
            print("gw_rev:", self.gw_rev)
            self.core.break_realtime()
        assert gw_rev == self.gw_rev
        delay(.1*ms)  # slack

        # allow a few errors during startup and alignment since boot
        if self.get_crc_err() > 20:
            raise ValueError("large number of frame CRC errors")
        delay(.1*ms)  # slack

        # determine the origin for frame-aligned timestamps
        self.measure_frame_timestamp()
        if self.frame_tstamp < 0:
            raise ValueError("frame timestamp measurement timed out")
        delay(.1*ms)

        # reset
        self.set_cfg(dac_resetb=0, dac_sleep=1, dac_txena=0,
                     trf0_ps=1, trf1_ps=1,
                     att0_rstn=0, att1_rstn=0)
        self.set_leds(0x00)
        self.set_fan_mu(0)
        # bring dac out of reset, keep tx off
        self.set_cfg(clk_sel=self.clk_sel, dac_txena=0,
                     trf0_ps=1, trf1_ps=1,
                     att0_rstn=0, att1_rstn=0)
        delay(.1*ms)  # slack

        # crossing dac_clk (reference) edges with sync_dly
        # changes the optimal fifo_offset by 4
        self.set_sync_dly(self.sync_dly)

        # 4 wire SPI, sif4_enable
        self.dac_write(0x02, 0x0080)
        if self.dac_read(0x7f) != 0x5409:
            raise ValueError("DAC version readback invalid")
        delay(.1*ms)
        if self.dac_read(0x00) != 0x049c:
            raise ValueError("DAC config0 reset readback invalid")
        delay(.1*ms)

        t = self.get_dac_temperature()
        delay(.1*ms)
        if t < 10 or t > 90:
            raise ValueError("DAC temperature out of bounds")

        for data in self.dac_mmap:
            self.dac_write(data >> 16, data)
            delay(120*us)
        self.dac_sync()
        delay(40*us)

        # pll_ndivsync_ena disable
        config18 = self.dac_read(0x18)
        delay(.1*ms)
        self.dac_write(0x18, config18 & ~0x0800)

        patterns = [
            [0xf05a, 0x05af, 0x5af0, 0xaf05],  # test channel/iq/byte/nibble
            [0x7a7a, 0xb6b6, 0xeaea, 0x4545],  # datasheet pattern a
            [0x1a1a, 0x1616, 0xaaaa, 0xc6c6],  # datasheet pattern b
        ]
        # A data delay of 2*50 ps heuristically and reproducibly matches
        # FPGA+board+DAC skews. There is plenty of margin (>= 250 ps
        # either side) and no need to tune at runtime.
        # Parity provides another level of safety.
        for i in range(len(patterns)):
            delay(.5*ms)
            errors = self.dac_iotest(patterns[i])
            if errors:
                raise ValueError("DAC iotest failure")

        delay(2*ms)  # let it settle
        lvolt = self.dac_read(0x18) & 7
        delay(.1*ms)
        if lvolt < 2 or lvolt > 5:
            raise ValueError("DAC PLL lock failed, check clocking")

        if self.tune_fifo_offset:
            fifo_offset = self.dac_tune_fifo_offset()
            if debug:
                print("fifo_offset:", fifo_offset)
                self.core.break_realtime()

        # self.dac_write(0x20, 0x0000)  # stop fifo sync
        # alarm = self.get_sta() & 1
        # delay(.1*ms)
        self.clear_dac_alarms()
        delay(2*ms)  # let it run a bit
        alarms = self.get_dac_alarms()
        delay(.1*ms)  # slack
        if alarms & ~0x0040:  # ignore PLL alarms (see DS)
            if debug:
                print("alarms:", alarms)
                self.core.break_realtime()
                # ignore alarms
            else:
                raise ValueError("DAC alarm")

        # avoid malformed output for: mixer_ena=1, nco_ena=0 after power up
        self.dac_write(self.dac_mmap[2] >> 16, self.dac_mmap[2] | (1 << 4))
        delay(40*us)
        self.dac_sync()
        delay(100*us)
        self.dac_write(self.dac_mmap[2] >> 16, self.dac_mmap[2])
        delay(40*us)
        self.dac_sync()
        delay(100*us)

        # power up trfs, release att reset
        self.set_cfg(clk_sel=self.clk_sel, dac_txena=0)

        for ch in range(2):
            channel = self.channel[ch]
            # test attenuator write and readback
            channel.set_att_mu(0x5a)
            if channel.get_att_mu() != 0x5a:
                raise ValueError("attenuator test failed")
            delay(.1*ms)
            channel.set_att_mu(0x00)  # maximum attenuation

            channel.set_servo(profile=0, enable=0, hold=1)

            if self.gw_rev == PHASER_GW_BASE:
                # test oscillators and DUC
                for i in range(len(channel.oscillator)):
                    oscillator = channel.oscillator[i]
                    asf = 0
                    if i == 0:
                        asf = 0x7fff
                    # 6pi/4 phase
                    oscillator.set_amplitude_phase_mu(asf=asf, pow=0xc000, clr=1)
                    delay(1*us)
                # 3pi/4
                channel.set_duc_phase_mu(0x6000)
                channel.set_duc_cfg(select=0, clr=1)
                self.duc_stb()
                delay(.1*ms)  # settle link, pipeline and impulse response
                data = channel.get_dac_data()
                delay(1*us)
                channel.oscillator[0].set_amplitude_phase_mu(asf=0, pow=0xc000,
                                                            clr=1)
                delay(.1*ms)
                sqrt2 = 0x5a81  # 0x7fff/sqrt(2)
                data_i = data & 0xffff
                data_q = (data >> 16) & 0xffff
                # allow ripple
                if (data_i < sqrt2 - 30 or data_i > sqrt2 or
                        abs(data_i - data_q) > 2):
                    raise ValueError("DUC+oscillator phase/amplitude test failed")

            if self.gw_rev == PHASER_GW_MIQRO:
                channel.miqro.reset()

            if is_baseband:
                continue

            if channel.trf_read(0) & 0x7f != 0x68:
                raise ValueError("TRF identification failed")
            delay(.1*ms)

            delay(.2*ms)
            for data in channel.trf_mmap:
                channel.trf_write(data)
            channel.cal_trf_vco()

            delay(2*ms)  # lock
            if not (self.get_sta() & (PHASER_STA_TRF0_LD << ch)):
                raise ValueError("TRF lock failure")
            delay(.1*ms)
            if channel.trf_read(0) & 0x1000:
                raise ValueError("TRF R_SAT_ERR")
            delay(.1*ms)
            channel.en_trf_out()

        # enable dac tx
        self.set_cfg(clk_sel=self.clk_sel)

    @kernel
    def write8(self, addr, data):
        """Write data to FPGA register.

        :param addr: Address to write to (7-bit)
        :param data: Data to write (8-bit)
        """
        rtio_output((self.channel_base << 8) | (addr & 0x7f) | 0x80, data)
        delay_mu(int64(self.t_frame))

    @kernel
    def read8(self, addr) -> TInt32:
        """Read from FPGA register.

        :param addr: Address to read from (7-bit)
        :return: Data read (8-bit)
        """
        rtio_output((self.channel_base << 8) | (addr & 0x7f), 0)
        response = rtio_input_data(self.channel_base)
        return response >> self.miso_delay

    @kernel
    def write16(self, addr, data: TInt32):
        """Write 16 bits to a sequence of FPGA registers."""
        self.write8(addr, data >> 8)
        self.write8(addr + 1, data)

    @kernel
    def write32(self, addr, data: TInt32):
        """Write 32 bits to a sequence of FPGA registers."""
        for offset in range(4):
            byte = data >> 24
            self.write8(addr + offset, byte)
            data <<= 8

    @kernel
    def read32(self, addr) -> TInt32:
        """Read 32 bits from a sequence of FPGA registers."""
        data = 0
        for offset in range(4):
            data <<= 8
            data |= self.read8(addr + offset)
            delay(20*us)  # slack
        return data

    @kernel
    def set_leds(self, leds):
        """Set the front panel LEDs.

        :param leds: LED settings (6-bit)
        """
        self.write8(PHASER_ADDR_LED, leds)

    @kernel
    def set_fan_mu(self, pwm):
        """Set the fan duty cycle in machine units.

        :param pwm: Duty cycle in machine units (8-bit)
        """
        self.write8(PHASER_ADDR_FAN, pwm)

    @kernel
    def set_fan(self, duty):
        """Set the fan duty cycle.

        :param duty: Duty cycle (0. to 1.)
        """
        pwm = int32(round(duty*255.))
        if pwm < 0 or pwm > 255:
            raise ValueError("duty cycle out of bounds")
        self.set_fan_mu(pwm)

    @kernel
    def set_cfg(self, clk_sel=0, dac_resetb=1, dac_sleep=0, dac_txena=1,
                trf0_ps=0, trf1_ps=0, att0_rstn=1, att1_rstn=1):
        """Set the configuration register.

        Each flag is a single bit (0 or 1).

        :param clk_sel: Select the external SMA clock input
        :param dac_resetb: Active low DAC reset pin
        :param dac_sleep: DAC sleep pin
        :param dac_txena: Enable DAC transmission pin
        :param trf0_ps: Quadrature upconverter 0 power save
        :param trf1_ps: Quadrature upconverter 1 power save
        :param att0_rstn: Active low attenuator 0 reset
        :param att1_rstn: Active low attenuator 1 reset
        """
        self.write8(PHASER_ADDR_CFG,
                    ((clk_sel & 1) << 0) | ((dac_resetb & 1) << 1) |
                    ((dac_sleep & 1) << 2) | ((dac_txena & 1) << 3) |
                    ((trf0_ps & 1) << 4) | ((trf1_ps & 1) << 5) |
                    ((att0_rstn & 1) << 6) | ((att1_rstn & 1) << 7))

    @kernel
    def get_sta(self):
        """Get the status register value.

        Bit flags are:

        * :const:`PHASER_STA_DAC_ALARM`: DAC alarm pin
        * :const:`PHASER_STA_TRF0_LD`: Quadrature upconverter 0 lock detect
        * :const:`PHASER_STA_TRF1_LD`: Quadrature upconverter 1 lock detect
        * :const:`PHASER_STA_TERM0`: ADC channel 0 termination indicator
        * :const:`PHASER_STA_TERM1`: ADC channel 1 termination indicator
        * :const:`PHASER_STA_SPI_IDLE`: SPI machine is idle and data registers can be read/written

        :return: Status register
        """
        return self.read8(PHASER_ADDR_STA)

    @kernel
    def get_crc_err(self):
        """Get the frame CRC error counter.

        :return: The number of frames with CRC mismatches sind the reset of the
            device. Overflows at 256.
        """
        return self.read8(PHASER_ADDR_CRC_ERR)

    @kernel
    def measure_frame_timestamp(self):
        """Measure the timestamp of an arbitrary frame and store it in ``self.frame_tstamp``.

        To be used as reference for aligning updates to the FastLink frames.
        See :meth:`get_next_frame_mu()`.
        """
        rtio_output(self.channel_base << 8, 0)  # read any register
        self.frame_tstamp = rtio_input_timestamp(now_mu() + 4 * self.t_frame, self.channel_base)
        delay(100 * us)

    @kernel
    def get_next_frame_mu(self):
        """Return the timestamp of the frame strictly after :meth:`~artiq.language.core.now_mu()`.

        Register updates (DUC, DAC, TRF, etc.) scheduled at this timestamp and multiples
        of ``self.t_frame`` later will have deterministic latency to output.
        """
        n = int64((now_mu() - self.frame_tstamp) / self.t_frame)
        return self.frame_tstamp + (n + 1) * self.t_frame

    @kernel
    def set_sync_dly(self, dly):
        """Set SYNC delay.

        :param dly: DAC SYNC delay setting (0 to 7)
        """
        if dly < 0 or dly > 7:
            raise ValueError("SYNC delay out of bounds")
        self.write8(PHASER_ADDR_SYNC_DLY, dly)

    @kernel
    def duc_stb(self):
        """Strobe the DUC configuration register update.

        Transfer staging to active registers.
        This affects both DUC channels.
        """
        self.write8(PHASER_ADDR_DUC_STB, 0)

    @kernel
    def spi_cfg(self, select, div, end, clk_phase=0, clk_polarity=0,
                half_duplex=0, lsb_first=0, offline=0, length=8):
        """Set the SPI machine configuration

        :param select: Chip selects to assert (DAC, TRF0, TRF1, ATT0, ATT1)
        :param div: SPI clock divider relative to 250 MHz fabric clock
        :param end: Whether to end the SPI transaction and deassert chip select
        :param clk_phase: SPI clock phase (sample on first or second edge)
        :param clk_polarity: SPI clock polarity (idle low or high)
        :param half_duplex: Read MISO data from MOSI wire
        :param lsb_first: Transfer the least significant bit first
        :param offline: Put the SPI interfaces offline and don't drive voltages
        :param length: SPI transfer length (1 to 8 bits)
        """
        if div < 2 or div > 257:
            raise ValueError("divider out of bounds")
        if length < 1 or length > 8:
            raise ValueError("length out of bounds")
        self.write8(PHASER_ADDR_SPI_SEL, select)
        self.write8(PHASER_ADDR_SPI_DIVLEN, (div - 2 >> 3) | (length - 1 << 5))
        self.write8(PHASER_ADDR_SPI_CFG,
                    ((offline & 1) << 0) | ((end & 1) << 1) |
                    ((clk_phase & 1) << 2) | ((clk_polarity & 1) << 3) |
                    ((half_duplex & 1) << 4) | ((lsb_first & 1) << 5))

    @kernel
    def spi_write(self, data):
        """Write 8 bits into the SPI data register and start/continue the
        transaction."""
        self.write8(PHASER_ADDR_SPI_DATW, data)

    @kernel
    def spi_read(self):
        """Read from the SPI input data register."""
        return self.read8(PHASER_ADDR_SPI_DATR)

    @kernel
    def dac_write(self, addr, data):
        """Write 16 bits to a DAC register.

        :param addr: Register address
        :param data: Register data to write
        """
        div = 34  # 100 ns min period
        t_xfer = self.core.seconds_to_mu((8 + 1)*div*4*ns)
        self.spi_cfg(select=PHASER_SEL_DAC, div=div, end=0)
        self.spi_write(addr)
        delay_mu(t_xfer)
        self.spi_write(data >> 8)
        delay_mu(t_xfer)
        self.spi_cfg(select=PHASER_SEL_DAC, div=div, end=1)
        self.spi_write(data)
        delay_mu(t_xfer)

    @kernel
    def dac_read(self, addr, div=34) -> TInt32:
        """Read from a DAC register.

        :param addr: Register address to read from
        :param div: SPI clock divider. Needs to be at least 250 (1 µs SPI
            clock) to read the temperature register.
        """
        t_xfer = self.core.seconds_to_mu((8 + 1)*div*4*ns)
        self.spi_cfg(select=PHASER_SEL_DAC, div=div, end=0)
        self.spi_write(addr | 0x80)
        delay_mu(t_xfer)
        self.spi_write(0)
        delay_mu(t_xfer)
        data = self.spi_read() << 8
        delay(20*us)  # slack
        self.spi_cfg(select=PHASER_SEL_DAC, div=div, end=1)
        self.spi_write(0)
        delay_mu(t_xfer)
        data |= self.spi_read()
        return data

    @kernel
    def get_dac_temperature(self) -> TInt32:
        """Read the DAC die temperature.

        :return: DAC temperature in degree Celsius
        """
        return self.dac_read(0x06, div=257) >> 8

    @kernel
    def dac_sync(self):
        """Trigger DAC synchronisation for both output channels.

        The DAC ``sif_sync`` is de-asserted, then asserted. The synchronisation is
        triggered on assertion.

        By default, the fine-mixer (NCO) and QMC are synchronised. This
        includes applying the latest register settings.

        The synchronisation sources may be configured through the ``syncsel_x``
        fields in the ``dac`` configuration dictionary (see :class:`Phaser`).

        .. note:: Synchronising the NCO clears the phase-accumulator.
        """
        config1f = self.dac_read(0x1f)
        delay(.4*ms)
        self.dac_write(0x1f, config1f & ~int32(1 << 1))
        self.dac_write(0x1f, config1f | (1 << 1))

    @kernel
    def set_dac_cmix(self, fs_8_step):
        """Set the DAC coarse mixer frequency for both channels.

        Use of the coarse mixer requires the DAC mixer to be enabled. The mixer
        can be configured via the ``dac`` configuration dictionary (see
        :class:`Phaser`).

        The selected coarse mixer frequency becomes active without explicit
        synchronisation.

        :param fs_8_step: coarse mixer frequency shift in 125 MHz steps. This
            should be an integer between -3 and 4 (inclusive).
        """
        # values recommended in data-sheet
        #         0       1       2       3       4       -3      -2      -1
        vals = [0b0000, 0b1000, 0b0100, 0b1100, 0b0010, 0b1010, 0b0001, 0b1110]
        cmix = vals[fs_8_step%8]
        config0d = self.dac_read(0x0d)
        delay(.1*ms)
        self.dac_write(0x0d, (config0d & ~(0b1111 << 12)) | (cmix << 12))

    @kernel
    def get_dac_alarms(self):
        """Read the DAC alarm flags.

        :return: DAC alarm flags (see datasheet for bit meaning)
        """
        return self.dac_read(0x05)

    @kernel
    def clear_dac_alarms(self):
        """Clear DAC alarm flags."""
        self.dac_write(0x05, 0x0000)

    @kernel
    def dac_iotest(self, pattern) -> TInt32:
        """Performs a DAC IO test according to the datasheet.

        :param pattern: List of four int32s containing the pattern
        :return: Bit error mask (16-bit)
        """
        if len(pattern) != 4:
            raise ValueError("pattern length out of bounds")
        for addr in range(len(pattern)):
            self.dac_write(0x25 + addr, pattern[addr])
            # repeat the pattern twice
            self.dac_write(0x29 + addr, pattern[addr])
        delay(.1*ms)
        for ch in range(2):
            channel = self.channel[ch]
            channel.set_duc_cfg(select=1)  # test
            # dac test data is i msb, q lsb
            data = pattern[2*ch] | (pattern[2*ch + 1] << 16)
            channel.set_dac_test(data)
            if channel.get_dac_data() != data:
                raise ValueError("DAC test data readback failed")
            delay(.1*ms)
        cfg = self.dac_read(0x01)
        delay(.1*ms)
        self.dac_write(0x01, cfg | 0x8000)  # iotest_ena
        self.dac_write(0x04, 0x0000)  # clear iotest_result
        delay(.2*ms)  # let it rip
        # no need to go through the alarm register,
        # just read the error mask
        # self.clear_dac_alarms()
        alarms = self.get_dac_alarms()
        delay(.1*ms)  # slack
        if alarms & 0x0080:  # alarm_from_iotest
            errors = self.dac_read(0x04)
            delay(.1*ms)  # slack
        else:
            errors = 0
        self.dac_write(0x01, cfg)  # clear config
        self.dac_write(0x04, 0x0000)  # clear iotest_result
        return errors

    @kernel
    def dac_tune_fifo_offset(self):
        """Scan through ``fifo_offset`` and configure midpoint setting.

        :return: Optimal ``fifo_offset`` setting with maximum margin to write
            pointer.
        """
        # expect two or three error free offsets:
        #
        # read offset 01234567
        # write pointer  w
        # distance    32101234
        # error free  x     xx
        config9 = self.dac_read(0x09)
        delay(.1*ms)
        good = 0
        for o in range(8):
            # set new fifo_offset
            self.dac_write(0x09, (config9 & 0x1fff) | (o << 13))
            self.clear_dac_alarms()
            delay(.1*ms)   # run
            alarms = self.get_dac_alarms()
            delay(.1*ms)  # slack
            if (alarms >> 11) & 0x7 == 0:  # any fifo alarm
                good |= 1 << o
        # if there are good offsets accross the wrap around
        # offset for computations
        if good & 0x81 == 0x81:
            good = ((good << 4) & 0xf0) | (good >> 4)
            offset = 4
        else:
            offset = 0
        # calculate mean
        sum = 0
        count = 0
        for o in range(8):
            if good & (1 << o):
                sum += o
                count += 1
        if count == 0:
            raise ValueError("no good fifo offset")
        best = ((sum // count) + offset) % 8
        self.dac_write(0x09, (config9 & 0x1fff) | (best << 13))
        return best


class PhaserChannel:
    """Phaser channel IQ pair.

    A Phaser channel contains:

    * multiple :class:`PhaserOscillator` (in the coredevice phy),
    * an interpolation chain and digital upconverter (DUC) on Phaser,
    * a :class:`Miqro` instance on Phaser,
    * several channel-specific settings in the DAC:

        * quadrature modulation compensation QMC
        * numerically controlled oscillator NCO or coarse mixer CMIX,

    * the analog quadrature upconverter (in the Phaser-Upconverter hardware variant), and
    * a digitally controlled step attenuator.

    Attributes:

    * :attr:`oscillator`: List of five instances of :class:`PhaserOscillator`.
    * :attr:`miqro`: A :class:`Miqro`.

    .. note:: The amplitude sum of the oscillators must be less than one to
        avoid clipping or overflow. If any of the DDS or DUC frequencies are
        non-zero, it is not sufficient to ensure that the sum in each
        quadrature is within range.

    .. note:: The interpolation filter on Phaser has an intrinsic sinc-like
        overshoot in its step response. That overshoot is a direct consequence
        of its near-brick-wall frequency response. For large and wide-band
        changes in oscillator parameters, the overshoot can lead to clipping
        or overflow after the interpolation. Either band-limit any changes
        in the oscillator parameters or back off the amplitude sufficiently.
        Miqro is not affected by this, but both the oscillators and Miqro can
        be affected by intrinsic overshoot of the interpolator on the DAC.
    """
    kernel_invariants = {"index", "phaser", "trf_mmap"}

    def __init__(self, phaser, index, trf):
        self.phaser = phaser
        self.index = index
        self.trf_mmap = TRF372017(trf).get_mmap()

        self.oscillator = [PhaserOscillator(self, osc) for osc in range(5)]
        self.miqro = Miqro(self)

    @kernel
    def get_dac_data(self) -> TInt32:
        """Get a sample of the current DAC data.

        The data is split accross multiple registers and thus the data
        is only valid if constant.

        :return: DAC data as 32-bit IQ. I/DACA/DACC in the 16 LSB,
            Q/DACB/DACD in the 16 MSB
        """
        return self.phaser.read32(PHASER_ADDR_DAC0_DATA + (self.index << 4))

    @kernel
    def set_dac_test(self, data: TInt32):
        """Set the DAC test data.

        :param data: 32-bit IQ test data, I/DACA/DACC in the 16 LSB,
            Q/DACB/DACD in the 16 MSB
        """
        self.phaser.write32(PHASER_ADDR_DAC0_TEST + (self.index << 4), data)

    @kernel
    def set_duc_cfg(self, clr=0, clr_once=0, select=0):
        """Set the digital upconverter (DUC) and interpolator configuration.

        :param clr: Keep the phase accumulator cleared (persistent)
        :param clr_once: Clear the phase accumulator for one cycle
        :param select: Select the data to send to the DAC (0: DUC data, 1: test
            data, other values: reserved)
        """
        self.phaser.write8(PHASER_ADDR_DUC0_CFG + (self.index << 4),
                           ((clr & 1) << 0) | ((clr_once & 1) << 1) |
                           ((select & 3) << 2))

    @kernel
    def set_duc_frequency_mu(self, ftw):
        """Set the DUC frequency.

        :param ftw: DUC frequency tuning word (32-bit)
        """
        self.phaser.write32(PHASER_ADDR_DUC0_F + (self.index << 4), ftw)

    @kernel
    def set_duc_frequency(self, frequency):
        """Set the DUC frequency in SI units.

        :param frequency: DUC frequency in Hz (passband from -200 MHz to
            200 MHz, wrapping around at +- 250 MHz)
        """
        ftw = int32(round(frequency*((1 << 30)/(125*MHz))))
        self.set_duc_frequency_mu(ftw)

    @kernel
    def set_duc_phase_mu(self, pow):
        """Set the DUC phase offset.

        :param pow: DUC phase offset word (16-bit)
        """
        addr = PHASER_ADDR_DUC0_P + (self.index << 4)
        self.phaser.write8(addr, pow >> 8)
        self.phaser.write8(addr + 1, pow)

    @kernel
    def set_duc_phase(self, phase):
        """Set the DUC phase in SI units.

        :param phase: DUC phase in turns
        """
        pow = int32(round(phase*(1 << 16)))
        self.set_duc_phase_mu(pow)

    @kernel
    def set_nco_frequency_mu(self, ftw):
        """Set the NCO frequency.

        This method stages the new NCO frequency, but does not apply it.

        Use of the DAC-NCO requires the DAC mixer and NCO to be enabled. These
        can be configured via the ``dac`` configuration dictionary (see 
        :class:`Phaser`).

        :param ftw: NCO frequency tuning word (32-bit)
        """
        self.phaser.dac_write(0x15 + (self.index << 1), ftw >> 16)
        self.phaser.dac_write(0x14 + (self.index << 1), ftw)

    @kernel
    def set_nco_frequency(self, frequency):
        """Set the NCO frequency in SI units.

        This method stages the new NCO frequency, but does not apply it.

        Use of the DAC-NCO requires the DAC mixer and NCO to be enabled. These
        can be configured via the ``dac`` configuration dictionary (see
        :class:`Phaser`).

        :param frequency: NCO frequency in Hz (passband from -400 MHz
            to 400 MHz, wrapping around at +- 500 MHz)
        """
        ftw = int32(round(frequency*((1 << 30)/(250*MHz))))
        self.set_nco_frequency_mu(ftw)

    @kernel
    def set_nco_phase_mu(self, pow):
        """Set the NCO phase offset.

        By default, the new NCO phase applies on completion of the SPI
        transfer. This also causes a staged NCO frequency to be applied.
        Different triggers for applying NCO settings may be configured through
        the ``syncsel_mixerxx`` fields in the ``dac`` configuration dictionary (see
        :class:`Phaser`).

        Use of the DAC-NCO requires the DAC mixer and NCO to be enabled. These
        can be configured via the ``dac`` configuration dictionary.

        :param pow: NCO phase offset word (16-bit)
        """
        self.phaser.dac_write(0x12 + self.index, pow)

    @kernel
    def set_nco_phase(self, phase):
        """Set the NCO phase in SI units.

        By default, the new NCO phase applies on completion of the SPI
        transfer. This also causes a staged NCO frequency to be applied.
        Different triggers for applying NCO settings may be configured through
        the ``syncsel_mixerxx`` fields in the ``dac`` configuration dictionary (see
        :class:`Phaser`).

        Use of the DAC-NCO requires the DAC mixer and NCO to be enabled. These
        can be configured via the ``dac`` configuration dictionary.

        :param phase: NCO phase in turns
        """
        pow = int32(round(phase*(1 << 16)))
        self.set_nco_phase_mu(pow)

    @kernel
    def set_att_mu(self, data):
        """Set channel attenuation.

        :param data: Attenuator data in machine units (8-bit)
        """
        div = 34  # 30 ns min period
        t_xfer = self.phaser.core.seconds_to_mu((8 + 1)*div*4*ns)
        self.phaser.spi_cfg(select=PHASER_SEL_ATT0 << self.index, div=div,
                            end=1)
        self.phaser.spi_write(data)
        delay_mu(t_xfer)

    @kernel
    def set_att(self, att):
        """Set channel attenuation in SI units.

        :param att: Attenuation in dB
        """
        # 2 lsb are inactive, resulting in 8 LSB per dB
        data = 0xff - int32(round(att*8))
        if data < 0 or data > 0xff:
            raise ValueError("attenuation out of bounds")
        self.set_att_mu(data)

    @kernel
    def get_att_mu(self) -> TInt32:
        """Read current attenuation.

        The current attenuation value is read without side effects.

        :return: Current attenuation in machine units
        """
        div = 34
        t_xfer = self.phaser.core.seconds_to_mu((8 + 1)*div*4*ns)
        self.phaser.spi_cfg(select=PHASER_SEL_ATT0 << self.index, div=div,
                            end=0)
        self.phaser.spi_write(0)
        delay_mu(t_xfer)
        data = self.phaser.spi_read()
        delay(20*us)  # slack
        self.phaser.spi_cfg(select=PHASER_SEL_ATT0 << self.index, div=div,
                            end=1)
        self.phaser.spi_write(data)
        delay_mu(t_xfer)
        return data

    @kernel
    def trf_write(self, data, readback=False):
        """Write 32 bits to quadrature upconverter register.

        :param data: Register data (32-bit) containing encoded address
        :param readback: Whether to return the read back MISO data
        """
        div = 34  # 50 ns min period
        t_xfer = self.phaser.core.seconds_to_mu((8 + 1)*div*4*ns)
        read = 0
        end = 0
        clk_phase = 0
        if readback:
            clk_phase = 1
        for i in range(4):
            if i == 0 or i == 3:
                if i == 3:
                    end = 1
                self.phaser.spi_cfg(select=PHASER_SEL_TRF0 << self.index,
                                    div=div, lsb_first=1, clk_phase=clk_phase,
                                    end=end)
            self.phaser.spi_write(data)
            data >>= 8
            delay_mu(t_xfer)
            if readback:
                read >>= 8
                read |= self.phaser.spi_read() << 24
                delay(20*us)  # slack
        return read

    @kernel
    def trf_read(self, addr, cnt_mux_sel=0) -> TInt32:
        """Quadrature upconverter register read.

        :param addr: Register address to read (0 to 7)
        :param cnt_mux_sel: Report VCO counter min or max frequency
        :return: Register data (32-bit)
        """
        self.trf_write(0x80000008 | (addr << 28) | (cnt_mux_sel << 27))
        # single clk pulse with ~LE to start readback
        self.phaser.spi_cfg(select=0, div=34, end=1, length=1)
        self.phaser.spi_write(0)
        delay((1 + 1)*34*4*ns)
        return self.trf_write(0x00000008 | (cnt_mux_sel << 27),
                              readback=True)

    @kernel
    def cal_trf_vco(self):
        """Start calibration of the upconverter (hardware variant) VCO.

        TRF outputs should be disabled during VCO calibration.
        """
        self.trf_write(self.trf_mmap[1] | (1 << 31))

    @kernel
    def en_trf_out(self, rf=1, lo=0):
        """Enable the rf/lo outputs of the upconverter (hardware variant).

        :param rf: 1 to enable RF output, 0 to disable
        :param lo: 1 to enable LO output, 0 to disable
        """
        data = self.trf_read(0xc)
        delay(0.1 * ms)
        # set RF and LO output bits
        data = data | (1 << 12) | (1 << 13) | (1 << 14)
        # clear to enable output
        if rf == 1:
            data = data ^ (1 << 14)
        if lo == 1:
            data = data ^ ((1 << 12) | (1 << 13))
        self.trf_write(data)

    @kernel
    def set_servo(self, profile=0, enable=0, hold=0):
        """Set the servo configuration.

        :param enable: 1 to enable servo, 0 to disable servo (default). If disabled,
            the servo is bypassed and hold is enforced since the control loop is broken.
        :param hold: 1 to hold the servo IIR filter output constant, 0 for normal operation.
        :param profile: Profile index to select for channel. (0 to 3)
        """
        if (profile < 0) or (profile > 3):
            raise ValueError("invalid profile index")
        addr = PHASER_ADDR_SERVO_CFG0 + self.index
        # enforce hold if the servo is disabled
        data = (profile << 2) | (((hold | ~enable) & 1) << 1) | (enable & 1)
        self.phaser.write8(addr, data)

    @kernel
    def set_iir_mu(self, profile, b0, b1, a1, offset):
        """Load a servo profile consiting of the three filter coefficients and an output offset.

        Avoid setting the IIR parameters of the currently active profile.

        The recurrence relation is (all data signed and MSB aligned):

        .. math::
            a_0 y_n = a_1 y_{n - 1} + b_0 x_n + b_1 x_{n - 1} + o

        Where:

            * :math:`y_n` and :math:`y_{n-1}` are the current and previous
              filter outputs, clipped to :math:`[0, 1[`.
            * :math:`x_n` and :math:`x_{n-1}` are the current and previous
              filter inputs in :math:`[-1, 1[`.
            * :math:`o` is the offset
            * :math:`a_0` is the normalization factor :math:`2^{14}`
            * :math:`a_1` is the feedback gain
            * :math:`b_0` and :math:`b_1` are the feedforward gains for the two
              delays

        See also :meth:`PhaserChannel.set_iir`.

        :param profile: Profile to set (0 to 3)
        :param b0: b0 filter coefficient (16-bit signed)
        :param b1: b1 filter coefficient (16-bit signed)
        :param a1: a1 filter coefficient (16-bit signed)
        :param offset: Output offset (16-bit signed)
        """
        if (profile < 0) or (profile > 3):
            raise ValueError("invalid profile index")
        # 32 byte-sized data registers per channel and 8 (2 bytes * (3 coefficients + 1 offset)) registers per profile
        addr = PHASER_ADDR_SERVO_DATA_BASE + (8 * profile) + (self.index * 32)
        for data in [b0, b1, a1, offset]:
            self.phaser.write16(addr, data)
            addr += 2

    @kernel
    def set_iir(self, profile, kp, ki=0., g=0., x_offset=0., y_offset=0.):
        """Set servo profile IIR coefficients.

        Avoid setting the IIR parameters of the currently active profile.

        Gains are given in units of output full per scale per input full scale.

        .. note:: Due to inherent constraints of the fixed point datatypes and IIR
            filters, the ``x_offset`` (setpoint) resolution depends on the selected
            gains. Low ``ki`` gains will lead to a low ``x_offset`` resolution.

        The transfer function is (up to time discretization and
        coefficient quantization errors):

        .. math::
            H(s) = k_p + \\frac{k_i}{s + \\frac{k_i}{g}}

        Where:
            * :math:`s = \\sigma + i\\omega` is the complex frequency
            * :math:`k_p` is the proportional gain
            * :math:`k_i` is the integrator gain
            * :math:`g` is the integrator gain limit

        :param profile: Profile number (0-3)
        :param kp: Proportional gain. This is usually negative (closed
            loop, positive ADC voltage, positive setpoint). When 0, this
            implements a pure I controller.
        :param ki: Integrator gain (rad/s). Equivalent to the gain at 1 Hz.
            When 0 (the default) this implements a pure P controller.
            Same sign as ``kp``.
        :param g: Integrator gain limit (1). When 0 (the default) the
            integrator gain limit is infinite. Same sign as ``ki``.
        :param x_offset: IIR input offset. Used as the negative
            setpoint when stabilizing to a desired input setpoint. Will
            be converted to an equivalent output offset and added to ``y_offset``.
        :param y_offset: IIR output offset.
        """
        NORM = 1 << SERVO_COEFF_SHIFT
        COEFF_MAX = 1 << SERVO_COEFF_WIDTH - 1
        DATA_MAX = 1 << SERVO_DATA_WIDTH - 1

        kp *= NORM
        if ki == 0.:
            # pure P
            a1 = 0
            b1 = 0
            b0 = int(round(kp))
        else:
            # I or PI
            ki *= NORM*SERVO_T_CYCLE/2.
            if g == 0.:
                c = 1.
                a1 = NORM
            else:
                c = 1./(1. + ki/(g*NORM))
                a1 = int(round((2.*c - 1.)*NORM))
            b0 = int(round(kp + ki*c))
            b1 = int(round(kp + (ki - 2.*kp)*c))
            if b1 == -b0:
                raise ValueError("low integrator gain and/or gain limit")

        if (b0 >= COEFF_MAX or b0 < -COEFF_MAX or
                b1 >= COEFF_MAX or b1 < -COEFF_MAX):
            raise ValueError("high gains")

        forward_gain = (b0 + b1) * (1 << SERVO_DATA_WIDTH - 1 - SERVO_COEFF_SHIFT)
        effective_offset = int(round(DATA_MAX * y_offset + forward_gain * x_offset))

        self.set_iir_mu(profile, b0, b1, a1, effective_offset)



class PhaserOscillator:
    """Phaser IQ channel oscillator (NCO/DDS).

    .. note:: Latencies between oscillators within a channel and between
        oscillator parameters (amplitude and phase/frequency) are deterministic
        (with respect to the 25 MS/s sample clock) but not matched.
    """
    kernel_invariants = {"channel", "base_addr"}

    def __init__(self, channel, index):
        self.channel = channel
        self.base_addr = ((self.channel.phaser.channel_base + 1 +
                           2*self.channel.index) << 8) | index

    @kernel
    def set_frequency_mu(self, ftw):
        """Set Phaser MultiDDS frequency tuning word.

        :param ftw: Frequency tuning word (32-bit)
        """
        rtio_output(self.base_addr, ftw)

    @kernel
    def set_frequency(self, frequency):
        """Set Phaser MultiDDS frequency.

        :param frequency: Frequency in Hz (passband from -10 MHz to 10 MHz,
            wrapping around at +- 12.5 MHz)
        """
        ftw = int32(round(frequency*((1 << 30)/(6.25*MHz))))
        self.set_frequency_mu(ftw)

    @kernel
    def set_amplitude_phase_mu(self, asf=0x7fff, pow=0, clr=0):
        """Set Phaser MultiDDS amplitude, phase offset and accumulator clear.

        :param asf: Amplitude (15-bit)
        :param pow: Phase offset word (16-bit)
        :param clr: Clear the phase accumulator (persistent)
        """
        data = (asf & 0x7fff) | ((clr & 1) << 15) | (pow << 16)
        rtio_output(self.base_addr + (1 << 8), data)

    @kernel
    def set_amplitude_phase(self, amplitude, phase=0., clr=0):
        """Set Phaser MultiDDS amplitude and phase.

        :param amplitude: Amplitude in units of full scale
        :param phase: Phase in turns
        :param clr: Clear the phase accumulator (persistent)
        """
        asf = int32(round(amplitude*0x7fff))
        if asf < 0 or asf > 0x7fff:
            raise ValueError("amplitude out of bounds")
        pow = int32(round(phase*(1 << 16)))
        self.set_amplitude_phase_mu(asf, pow, clr)


class Miqro:
    """
    Miqro pulse generator.

    A Miqro instance represents one RF output. The DSP components are fully
    contained in the Phaser gateware. The output is generated by with
    the following data flow:

    **Oscillators**

    * There are ``n_osc = 16`` oscillators with oscillator IDs ``0``... ``n_osc-1``.
    * Each oscillator outputs one tone at any given time

        * I/Q (quadrature, a.k.a. complex) 2x16-bit signed data
          at tau = 4 ns sample intervals, 250 MS/s, Nyquist 125 MHz, bandwidth 200 MHz
          (from f = -100..+100 MHz, taking into account the interpolation anti-aliasing
          filters in subsequent interpolators),
        * 32-bit frequency (f) resolution (~ 1/16 Hz),
        * 16-bit unsigned amplitude (a) resolution
        * 16-bit phase offset (p) resolution

    * The output phase ``p'`` of each oscillator at time ``t`` (boot/reset/initialization of the
      device at ``t=0``) is then ``p' = f*t + p (mod 1 turn)`` where ``f`` and ``p`` are the (currently
      active) profile frequency and phase offset.
    
    .. note :: 
        The terms  "phase coherent" and "phase tracking" are defined to refer to this
        choice of oscillator output phase ``p'``. Note that the phase offset ``p`` is not relative to
        (on top of previous phase/profiles/oscillator history).
        It is "absolute" in the sense that frequency ``f`` and phase offset ``p`` fully determine
        oscillator output phase ``p'`` at time ``t``. This is unlike typical DDS behavior.
    
    * Frequency, phase, and amplitude of each oscillator are configurable by selecting one of
      ``n_profiles = 32`` profiles ``0``... ``n_profile-1``. This selection is fast and can be 
      done for each pulse. The phase coherence defined above is guaranteed for each
      profile individually.
    * Note: one profile per oscillator (usually profile index 0) should be reserved
      for the NOP (no operation, identity) profile, usually with zero amplitude.
    * Data for each profile for each oscillator can be configured
      individually. Storing profile data should be considered "expensive".
    
    .. note:: 
        To refer to an operation as "expensive" does not mean it is impossible, 
        merely that it may take a significant amount of time and resources to 
        execute, such that it may be impractical when used often or during fast 
        pulse sequences. They are intended for use in calibration and initialization.  

    **Summation**

    * The oscillator outputs are added together (wrapping addition).
    * The user must ensure that the sum of oscillators outputs does not exceed the
      data range. In general that means that the sum of the amplitudes must not
      exceed one.

    **Shaper**

    * The summed complex output stream is then multiplied with a the complex-valued
      output of a triggerable shaper.
    * Triggering the shaper corresponds to passing a pulse from all oscillators to
      the RF output.
    * Selected profiles become active simultaneously (on the same output sample) when
      triggering the shaper with the first shaper output sample.
    * The shaper reads (replays) window samples from a memory of size ``n_window = 1 << 10``.
    * The window memory can be segmented by choosing different start indices
      to support different windows.
    * Each window memory segment starts with a header determining segment
      length and interpolation parameters.
    * The window samples are interpolated by a factor (rate change) between 1 and
      ``r = 1 << 12``.
    * The interpolation order is constant, linear, quadratic, or cubic. This
      corresponds to interpolation modes from rectangular window (1st order CIC)
      or zero order hold) to Parzen window (4th order CIC or cubic spline).
    * This results in support for single shot pulse lengths (envelope support) between
      tau and a bit more than ``r * n_window * tau = (1 << 12 + 10) tau ~ 17 ms``.
    * Windows can be configured to be head-less and/or tail-less, meaning, they
      do not feed zero-amplitude samples into the shaper before and after
      each window respectively. This is used to implement pulses with arbitrary
      length or CW output.

    **Overall properties**

    * The DAC may upconvert the signal by applying a frequency offset ``f1`` with
      phase ``p1``.
    * In the Upconverter Phaser variant, the analog quadrature upconverter
      applies another frequency of ``f2`` and phase ``p2``.
    * The resulting phase of the signal from one oscillator at the SMA output is
      ``(f + f1 + f2)*t + p + s(t - t0) + p1 + p2 (mod 1 turn)``
      where ``s(t - t0)`` is the phase of the interpolated
      shaper output, and ``t0`` is the trigger time (fiducial of the shaper).
      Unsurprisingly the frequency is the derivative of the phase.
    * Group delays between pulse parameter updates are matched across oscillators,
      shapers, and channels.
    * The minimum time to change profiles and phase offsets is ``~128 ns`` (estimate, TBC).
      This is the minimum pulse interval.
      The sustained pulse rate of the RTIO PHY/Fastlink is one pulse per Fastlink frame
      (may be increased, TBC).
    """

    def __init__(self, channel):
        self.channel = channel
        self.base_addr = (self.channel.phaser.channel_base + 1 +
                self.channel.index) << 8

    @kernel
    def reset(self):
        """Establish no-output profiles and no-output window and execute them.

        This establishes the first profile (index 0) on all oscillators as zero
        amplitude, creates a trivial window (one sample with zero amplitude,
        minimal interpolation), and executes a corresponding pulse.
        """
        for osc in range(16):
            self.set_profile_mu(osc, profile=0, ftw=0, asf=0)
            delay(20*us)
        self.set_window_mu(start=0, iq=[0], order=0)
        self.pulse(window=0, profiles=[0])

    @kernel
    def set_profile_mu(self, oscillator, profile, ftw, asf, pow_=0):
        """Store an oscillator profile (machine units).

        :param oscillator: Oscillator index (0 to 15)
        :param profile: Profile index (0 to 31)
        :param ftw: Frequency tuning word (32-bit signed integer on a 250 MHz clock)
        :param asf: Amplitude scale factor (16-bit unsigned integer)
        :param pow_: Phase offset word (16-bit integer)
        """
        if oscillator >= 16:
            raise ValueError("invalid oscillator index")
        if profile >= 32:
            raise ValueError("invalid profile index")
        self.channel.phaser.write16(PHASER_ADDR_MIQRO_MEM_ADDR,
                (self.channel.index << 15) | PHASER_MIQRO_SEL_PROFILE |
                (oscillator << 6) | (profile << 1))
        self.channel.phaser.write32(PHASER_ADDR_MIQRO_MEM_DATA, ftw)
        self.channel.phaser.write32(PHASER_ADDR_MIQRO_MEM_DATA,
            (asf & 0xffff) | (pow_ << 16))

    @kernel
    def set_profile(self, oscillator, profile, frequency, amplitude, phase=0.):
        """Store an oscillator profile.

        :param oscillator: Oscillator index (0 to 15)
        :param profile: Profile index (0 to 31)
        :param frequency: Frequency in Hz (passband -100 to 100 MHz).
            Interpreted in the Nyquist sense, i.e. aliased.
        :param amplitude: Amplitude in units of full scale (0. to 1.)
        :param phase: Phase in turns. See :class:`Miqro` for a definition of
            phase in this context.
        :return: The quantized 32-bit frequency tuning word
        """
        ftw = int32(round(frequency*((1 << 30)/(62.5*MHz))))
        asf = int32(round(amplitude*0xffff))
        if asf < 0 or asf > 0xffff:
            raise ValueError("amplitude out of bounds")
        pow_ = int32(round(phase*(1 << 16)))
        self.set_profile_mu(oscillator, profile, ftw, asf, pow_)
        return ftw

    @kernel
    def set_window_mu(self, start, iq, rate=1, shift=0, order=3, head=1, tail=1):
        """Store a window segment (machine units).

        :param start: Window start address (0 to 0x3ff)
        :param iq: List of IQ window samples. Each window sample is an integer
            containing the signed I part in the 16 LSB and the signed Q part in
            the 16 MSB. The maximum window length is 0x3fe. The user must
            ensure that this window does not overlap with other windows in the
            memory.
        :param rate: Interpolation rate change (1 to 1 << 12)
        :param shift: Interpolator amplitude gain compensation in powers of 2 (0 to 63)
        :param order: Interpolation order from 0 (corresponding to
            constant/rectangular window/zero-order-hold/1st order CIC interpolation)
            to 3 (corresponding to cubic/Parzen window/4th order CIC interpolation)
        :param head: Update the interpolator settings and clear its state at the start
            of the window. This also implies starting the envelope from zero.
        :param tail: Feed zeros into the interpolator after the window samples.
            In the absence of further pulses this will return the output envelope
            to zero with the chosen interpolation.
        :return: Next available window memory address after this segment.
        """
        if start >= 1 << 10:
            raise ValueError("start out of bounds")
        if len(iq) >= 1 << 10:
            raise ValueError("window length out of bounds")
        if rate < 1 or rate > 1 << 12:
            raise ValueError("rate out of bounds")
        if shift > 0x3f:
            raise ValueError("shift out of bounds")
        if order > 3:
            raise ValueError("order out of bounds")
        self.channel.phaser.write16(PHASER_ADDR_MIQRO_MEM_ADDR,
                (self.channel.index << 15) | start)
        self.channel.phaser.write32(PHASER_ADDR_MIQRO_MEM_DATA,
            (len(iq) & 0x3ff) |
            ((rate - 1) << 10) |
            (shift << 22) |
            (order << 28) |
            ((head & 1) << 30) |
            ((tail & 1) << 31)
        )
        for iqi in iq:
            self.channel.phaser.write32(PHASER_ADDR_MIQRO_MEM_DATA, iqi)
            delay(20*us)  # slack for long windows
        return (start + 1 + len(iq)) & 0x3ff

    @kernel
    def set_window(self, start, iq, period=4*ns, order=3, head=1, tail=1):
        """Store a window segment.

        :param start: Window start address (0 to 0x3ff)
        :param iq: List of IQ window samples. Each window sample is a pair of
            two float numbers -1 to 1, one for each I and Q in units of full scale.
            The maximum window length is 0x3fe. The user must ensure that this window
            does not overlap with other windows in the memory.
        :param period: Desired window sample period in SI units (4*ns to (4 << 12)*ns).
        :param order: Interpolation order from 0 (corresponding to
            constant/zero-order-hold/1st order CIC interpolation) to 3 (corresponding
            to cubic/Parzen/4th order CIC interpolation)
        :param head: Update the interpolator settings and clear its state at the start
            of the window. This also implies starting the envelope from zero.
        :param tail: Feed zeros into the interpolator after the window samples.
            In the absence of further pulses this will return the output envelope
            to zero with the chosen interpolation.
        :return: Actual sample period in SI units
        """
        rate = int32(round(period/(4*ns)))
        gain = 1.
        for _ in range(order):
            gain *= rate
        shift = 0
        while gain >= 2.:
            shift += 1
            gain *= .5
        scale = ((1 << 15) - 1)/gain
        iq_mu = [
            (int32(round(iqi[0]*scale)) & 0xffff) |
            (int32(round(iqi[1]*scale)) << 16)
            for iqi in iq
        ]
        self.set_window_mu(start, iq_mu, rate, shift, order, head, tail)
        return (len(iq) + order)*rate*4*ns

    @kernel
    def encode(self, window, profiles, data):
        """Encode window and profile selection.

        :param window: Window start address (0 to 0x3ff)
        :param profiles: List of profile indices for the oscillators. Maximum
            length 16. Unused oscillators will be set to profile 0.
        :param data: List of integers to store the encoded data words into.
            Unused entries will remain untouched. Must contain at least three
            lements if all oscillators are used and should be initialized to
            zeros.
        :return: Number of words from `data` used.
        """
        if len(profiles) > 16:
            raise ValueError("too many oscillators")
        if window > 0x3ff:
            raise ValueError("window start out of bounds")
        data[0] = window
        word = 0
        idx = 10
        for profile in profiles:
            if profile > 0x1f:
                raise ValueError("profile out of bounds")
            if idx > 32 - 5:
                word += 1
                idx = 0
            data[word] |= profile << idx
            idx += 5
        return word + 1

    @kernel
    def pulse_mu(self, data):
        """Emit a pulse (encoded)

        The pulse fiducial timing resolution is 4 ns.

        :param data: List of up to 3 words containing an encoded MIQRO pulse as
            returned by :meth:`encode`.
        """
        word = len(data)
        delay_mu(-8*word)  # back shift to align
        while word > 0:
            word -= 1
            delay_mu(8)
            # final write sets pulse stb
            rtio_output(self.base_addr + word, data[word])

    @kernel
    def pulse(self, window, profiles):
        """Emit a pulse

        This encodes the window and profiles (see :meth:`encode`) and emits them
        (see :meth:`pulse_mu`).

        :param window: Window start address (0 to 0x3ff)
        :param profiles: List of profile indices for the oscillators. Maximum
            length 16. Unused oscillators will select profile 0.
        """
        data = [0, 0, 0]
        words = self.encode(window, profiles, data)
        self.pulse_mu(data[:words])
