from artiq.language.core import kernel, delay_mu, delay
from artiq.coredevice.rtio import rtio_output, rtio_input_data
from artiq.language.units import us, ns, ms, MHz, dB
from artiq.language.types import TInt32
from artiq.coredevice.dac34h84 import DAC34H84
from artiq.coredevice.trf372017 import TRF372017


PHASER_BOARD_ID = 19
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


class Phaser:
    """Phaser 4-channel, 16-bit, 1 GS/s DAC coredevice driver.

    Phaser contains a 4 channel, 1 GS/s DAC chip with integrated upconversion,
    quadrature modulation compensation and interpolation features.

    The coredevice produces 2 IQ (in-phase and quadrature) data streams with 25
    MS/s and 14 bit per quadrature. Each data stream supports 5 independent
    numerically controlled IQ oscillators (NCOs, DDSs with 32 bit frequency, 16
    bit phase, 15 bit amplitude, and phase accumulator clear functionality)
    added together. See :class:`PhaserChannel` and :class:`PhaserOscillator`.

    Together with a data clock, framing marker, a checksum and metadata for
    register access the streams are sent in groups of 8 samples over 1.5 Gb/s
    FastLink via a single EEM connector from coredevice to Phaser.

    On Phaser in the FPGA the data streams are buffered and interpolated
    from 25 MS/s to 500 MS/s 16 bit followed by a 500 MS/s digital upconverter
    with adjustable frequency and phase. The interpolation passband is 20 MHz
    wide, passband ripple is less than 1e-3 amplitude, stopband attenuation
    is better than 75 dB at offsets > 15 MHz and better than 90 dB at offsets
    > 30 MHz.

    The four 16 bit 500 MS/s DAC data streams are sent via a 32 bit parallel
    LVDS bus operating at 1 Gb/s per pin pair and processed in the DAC (Texas
    Instruments DAC34H84). On the DAC 2x interpolation, sinx/x compensation,
    quadrature modulator compensation, fine and coarse mixing as well as group
    delay capabilities are available.

    The latency/group delay from the RTIO events setting
    :class:`PhaserOscillator` or :class:`PhaserChannel` DUC parameters all the
    way to the DAC outputs is deterministic. This enables deterministic
    absolute phase with respect to other RTIO input and output events.

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

    .. note:: Various register settings of the DAC and the quadrature
        upconverters are available to be modified through the `dac`, `trf0`,
        `trf1` dictionaries. These can be set through the device database
        (`device_db.py`). The settings are frozen during instantiation of the
        class and applied during `init()`. See the :class:`DAC34H84` and
        :class:`TRF372017` source for details.

    .. note:: To establish deterministic latency between RTIO time base and DAC
        output, the DAC FIFO read pointer value (`fifo_offset`) must be
        fixed. If `tune_fifo_offset=True` (the default) a value with maximum
        margin is determined automatically by `dac_tune_fifo_offset` each time
        `init()` is called. This value should be used for the `fifo_offset` key
        of the `dac` settings of Phaser in `device_db.py` and automatic
        tuning should be disabled by `tune_fifo_offset=False`.

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

    Attributes:

    * :attr:`channel`: List of two :class:`PhaserChannel`
        To access oscillators, digital upconverters, PLL/VCO analog
        quadrature upconverters and attenuators.
    """
    kernel_invariants = {"core", "channel_base", "t_frame", "miso_delay",
                         "dac_mmap"}

    def __init__(self, dmgr, channel_base, miso_delay=1, tune_fifo_offset=True,
                 clk_sel=0, sync_dly=0, dac=None, trf0=None, trf1=None,
                 core_device="core"):
        self.channel_base = channel_base
        self.core = dmgr.get(core_device)
        # TODO: auto-align miso-delay in phy
        self.miso_delay = miso_delay
        # frame duration in mu (10 words, 8 clock cycles each 4 ns)
        # self.core.seconds_to_mu(10*8*4*ns)  # unfortunately this returns 319
        assert self.core.ref_period == 1*ns
        self.t_frame = 10*8*4
        self.clk_sel = clk_sel
        self.tune_fifo_offset = tune_fifo_offset
        self.sync_dly = sync_dly

        self.dac_mmap = DAC34H84(dac).get_mmap()

        self.channel = [PhaserChannel(self, ch, trf)
                        for ch, trf in enumerate([trf0, trf1])]

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
        delay(.1*ms)  # slack

        # allow a few errors during startup and alignment since boot
        if self.get_crc_err() > 20:
            raise ValueError("large number of frame CRC errors")
        delay(.1*ms)  # slack

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
                print(fifo_offset)
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
                print(alarms)
                self.core.break_realtime()
                # ignore alarms
            else:
                raise ValueError("DAC alarm")

        # power up trfs, release att reset
        self.set_cfg(clk_sel=self.clk_sel, dac_txena=0)

        for ch in range(2):
            channel = self.channel[ch]
            # test attenuator write and readback
            channel.set_att_mu(0x5a)
            if channel.get_att_mu() != 0x5a:
                raise ValueError("attenuator test failed")
            delay(.1*ms)
            channel.set_att_mu(0x00)  # minimum attenuation

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
            delay(.1*ms)
            sqrt2 = 0x5a81  # 0x7fff/sqrt(2)
            data_i = data & 0xffff
            data_q = (data >> 16) & 0xffff
            # allow ripple
            if (data_i < sqrt2 - 30 or data_i > sqrt2 or
                    abs(data_i - data_q) > 2):
                raise ValueError("DUC+oscillator phase/amplitude test failed")

            if is_baseband:
                continue

            if channel.trf_read(0) & 0x7f != 0x68:
                raise ValueError("TRF identification failed")
            delay(.1*ms)

            delay(.2*ms)
            for data in channel.trf_mmap:
                channel.trf_write(data)

            delay(2*ms)  # lock
            if not (self.get_sta() & (PHASER_STA_TRF0_LD << ch)):
                raise ValueError("TRF lock failure")
            delay(.1*ms)
            if channel.trf_read(0) & 0x1000:
                raise ValueError("TRF R_SAT_ERR")
            delay(.1*ms)

        # enable dac tx
        self.set_cfg(clk_sel=self.clk_sel)

    @kernel
    def write8(self, addr, data):
        """Write data to FPGA register.

        :param addr: Address to write to (7 bit)
        :param data: Data to write (8 bit)
        """
        rtio_output((self.channel_base << 8) | (addr & 0x7f) | 0x80, data)
        delay_mu(int64(self.t_frame))

    @kernel
    def read8(self, addr) -> TInt32:
        """Read from FPGA register.

        :param addr: Address to read from (7 bit)
        :return: Data read (8 bit)
        """
        rtio_output((self.channel_base << 8) | (addr & 0x7f), 0)
        response = rtio_input_data(self.channel_base)
        return response >> self.miso_delay

    @kernel
    def write32(self, addr, data: TInt32):
        """Write 32 bit to a sequence of FPGA registers."""
        for offset in range(4):
            byte = data >> 24
            self.write8(addr + offset, byte)
            data <<= 8

    @kernel
    def read32(self, addr) -> TInt32:
        """Read 32 bit from a sequence of FPGA registers."""
        data = 0
        for offset in range(4):
            data <<= 8
            data |= self.read8(addr + offset)
            delay(20*us)  # slack
        return data

    @kernel
    def set_leds(self, leds):
        """Set the front panel LEDs.

        :param leds: LED settings (6 bit)
        """
        self.write8(PHASER_ADDR_LED, leds)

    @kernel
    def set_fan_mu(self, pwm):
        """Set the fan duty cycle.

        :param pwm: Duty cycle in machine units (8 bit)
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
        """Write 16 bit to a DAC register.

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

        :param pattern: List of four int32 containing the pattern
        :return: Bit error mask (16 bits)
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
        """Scan through `fifo_offset` and configure midpoint setting.

        :return: Optimal `fifo_offset` setting with maximum margin to write
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
        best = ((sum // count) + offset) % 8
        self.dac_write(0x09, (config9 & 0x1fff) | (best << 13))
        return best


class PhaserChannel:
    """Phaser channel IQ pair.

    A Phaser channel contains:

    * multiple oscillators (in the coredevice phy),
    * an interpolation chain and digital upconverter (DUC) on Phaser,
    * several channel-specific settings in the DAC:

        * quadrature modulation compensation QMC
        * numerically controlled oscillator NCO or coarse mixer CMIX,

    * the analog quadrature upconverter (in the Phaser-Upconverter hardware variant), and
    * a digitally controlled step attenuator.

    Attributes:

    * :attr:`oscillator`: List of five :class:`PhaserOscillator`.

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
    """
    kernel_invariants = {"index", "phaser", "trf_mmap"}

    def __init__(self, phaser, index, trf):
        self.phaser = phaser
        self.index = index
        self.trf_mmap = TRF372017(trf).get_mmap()
        self.oscillator = [PhaserOscillator(self, osc) for osc in range(5)]

    @kernel
    def get_dac_data(self) -> TInt32:
        """Get a sample of the current DAC data.

        The data is split accross multiple registers and thus the data
        is only valid if constant.

        :return: DAC data as 32 bit IQ. I/DACA/DACC in the 16 LSB,
            Q/DACB/DACD in the 16 MSB
        """
        return self.phaser.read32(PHASER_ADDR_DAC0_DATA + (self.index << 4))

    @kernel
    def set_dac_test(self, data: TInt32):
        """Set the DAC test data.

        :param data: 32 bit IQ test data, I/DACA/DACC in the 16 LSB,
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

        :param ftw: DUC frequency tuning word (32 bit)
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

        :param pow: DUC phase offset word (16 bit)
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

        :param ftw: NCO frequency tuning word (32 bit)
        """
        self.phaser.dac_write(0x15 + (self.index << 1), ftw >> 16)
        self.phaser.dac_write(0x14 + (self.index << 1), ftw)

    @kernel
    def set_nco_frequency(self, frequency):
        """Set the NCO frequency in SI units.

        :param frequency: NCO frequency in Hz (passband from -400 MHz
            to 400 MHz, wrapping around at +- 500 MHz)
        """
        ftw = int32(round(frequency*((1 << 30)/(250*MHz))))
        self.set_nco_frequency_mu(ftw)

    @kernel
    def set_nco_phase_mu(self, pow):
        """Set the NCO phase offset.

        :param pow: NCO phase offset word (16 bit)
        """
        self.phaser.dac_write(0x12 + self.index, pow)

    @kernel
    def set_nco_phase(self, phase):
        """Set the NCO phase in SI units.

        :param phase: NCO phase in turns
        """
        pow = int32(round(phase*(1 << 16)))
        self.set_duc_phase_mu(pow)

    @kernel
    def set_att_mu(self, data):
        """Set channel attenuation.

        :param data: Attenuator data in machine units (8 bit)
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

        :param data: Register data (32 bit) containing encoded address
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
        :return: Register data (32 bit)
        """
        self.trf_write(0x80000008 | (addr << 28) | (cnt_mux_sel << 27))
        # single clk pulse with ~LE to start readback
        self.phaser.spi_cfg(select=0, div=34, end=1, length=1)
        self.phaser.spi_write(0)
        delay((1 + 1)*34*4*ns)
        return self.trf_write(0x00000008 | (cnt_mux_sel << 27),
                              readback=True)


class PhaserOscillator:
    """Phaser IQ channel oscillator (NCO/DDS).

    .. note:: Latencies between oscillators within a channel and between
        oscillator paramters (amplitude and phase/frequency) are deterministic
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

        :param ftw: Frequency tuning word (32 bit)
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

        :param asf: Amplitude (15 bit)
        :param pow: Phase offset word (16 bit)
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
