from artiq.language.core import kernel, delay_mu, delay
from artiq.coredevice.rtio import rtio_output, rtio_input_data
from artiq.language.units import us, ns
from artiq.language.types import TInt32


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
# PHASER_ADDR_RESERVED0 = 0x0f
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


class Phaser:
    """Phaser 4-channel, 16-bit, 1 GS/s DAC coredevice driver.

    Phaser contains a 4 channel, 1 GS/s DAC chip with integrated upconversion,
    quadrature modulation compensation and interpolation features.

    The coredevice produces 2 IQ data streams with 25 MS/s 14 bit. Each
    data stream supports 5 independent numerically controlled oscillators (NCOs)
    added together for each channel. Together with a data clock, framing
    marker, a checksum and metadata for register access the data is sent in
    groups of 8 samples over 1.5 Gb/s FastLink via a single EEM connector.

    On Phaser the data streams are buffered and interpolated from 25 MS/s to 500
    MS/s 16 bit followed by a 500 MS/s digital upconverter in the FPGA.

    The four 16 bit 500 MS/s DAC data streams are sent via a 32 bit parallel
    LVDS bus operating at 1 Gb/s per pin pair and processed in the DAC.

    The four analog DAC outputs are passed through anti-aliasing filters and In
    the baseband variant, the even channels feed 31.5 dB range and are
    available on the front panel. The odd outputs are available on MMCX
    connectors on board.

    In the upconverter variant, each of the two IQ (in-phase and quadrature)
    output pairs feeds a one quadrature upconverter with integrated PLL/VCO.
    The output from the upconverter passes through the step attenuator and is
    available at the front panel.

    The DAC, the TRF upconverters and the two attenuators are configured
    through a shared SPI bus that is accessed and controlled via FPGA
    registers.

    :param channel: Base RTIO channel number
    :param core_device: Core device name (default: "core")
    :param miso_delay: Fastlink MISO signal delay to account for cable
        and buffer round trip. This might be automated later.
    """
    kernel_invariants = {"core", "channel_base", "t_frame", "miso_delay"}

    def __init__(self, dmgr, channel_base, miso_delay=1, core_device="core"):
        self.channel_base = channel_base
        self.core = dmgr.get(core_device)
        self.miso_delay = miso_delay
        # frame duration in mu (10 words, 8 clock cycles each 4 ns)
        # self.core.seconds_to_mu(10*8*4*ns)  # unfortunately this returns 319
        assert self.core.ref_period == 1*ns
        self.t_frame = 10*8*4

    @kernel
    def init(self):
        """Initialize the board.

        Verifies board presence by reading the board ID register.
        Does not alter any state.
        """
        board_id = self.read8(PHASER_ADDR_BOARD_ID)
        if board_id != PHASER_BOARD_ID:
            raise ValueError("invalid board id")
        delay(20*us)  # slack

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
    def write16(self, addr, data: TInt32):
        """Write 16 bit to a sequence of FPGA registers."""
        self.write8(addr, data >> 8)
        self.write8(addr + 1, data)

    @kernel
    def read16(self, addr) -> TInt32:
        """Read 16 bit from a sequence of FPGA registers."""
        return (self.read8(addr) << 8) | self.read8(addr)

    @kernel
    def set_leds(self, leds):
        """Set the front panel LEDs.

        :param leds: LED settings (6 bit)
        """
        self.write8(PHASER_ADDR_LED, leds)

    @kernel
    def set_fan(self, duty):
        """Set the fan duty cycle.

        :param duty: Duty cycle (8 bit)
        """
        self.write8(PHASER_ADDR_FAN, duty)

    @kernel
    def set_cfg(self, clk_sel=0, dac_resetb=1, dac_sleep=0, dac_txena=1,
                trf0_ps=0, trf1_ps=0, att0_rstn=1, att1_rstn=1):
        """Set the configuration register.

        :param clk_sel: Select the external SMA clock input
        :param dac_resetb: Active low DAC reset pin
        :param dac_sleep: DAC sleep pin
        :param dac_txena: Enable DAC transmission pin
        :param trf0_ps: TRF0 upconverter power save
        :param trf1_ps: TRF1 upconverter power save
        :param att0_rstn: Active low attenuator 0 reset
        :param att1_rstn: Active low attenuator 1 reset
        """
        self.write8(PHASER_ADDR_CFG,
                    (clk_sel << 0) | (dac_resetb << 1) | (dac_sleep << 2) |
                    (dac_txena << 3) | (trf0_ps << 4) | (trf1_ps << 5) |
                    (att0_rstn << 6) | (att1_rstn << 7))

    @kernel
    def get_sta(self):
        """Get the status register value.

        Bit flags are:

        * `PHASER_STA_DAC_ALARM`: DAC alarm pin
        * `PHASER_STA_TRF0_LD`: TRF0 lock detect pin
        * `PHASER_STA_TRF1_LD`: TRF1 lock detect pin
        * `PHASER_STA_TERM0`: ADC channel 0 termination indicator
        * `PHASER_STA_TERM1`: ADC channel 1 termination indicator
        * `PHASER_STA_SPI_IDLE`: SPI machine is idle and data registers can be
            read/written

        :return: Status register
        """
        return self.read8(PHASER_ADDR_STA)

    @kernel
    def get_crc_err(self):
        """Get the frame CRC error counter."""
        return self.read8(PHASER_ADDR_CRC_ERR)

    @kernel
    def get_dac_data(self, ch) -> TInt32:
        """Get a sample of the current DAC data.

        The data is split accross multiple registers and thus the data
        is only valid if constant.

        :param ch: DAC channel pair (0 or 1)
        :return: DAC data as 32 bit IQ
        """
        data = 0
        for addr in range(4):
            data <<= 8
            data |= self.read8(PHASER_ADDR_DAC0_DATA + (ch << 4) + addr)
            delay(20*us)  # slack
        return data

    @kernel
    def set_dac_test(self, ch, data: TInt32):
        """Set the DAC test data.

        :param ch: DAC channel pair (0 or 1)
        :param data: 32 bit IQ test data
        """
        for addr in range(4):
            byte = data >> 24
            self.write8(PHASER_ADDR_DAC0_TEST + (ch << 4) + addr, byte)
            data <<= 8

    @kernel
    def set_duc_cfg(self, ch, clr=0, clr_once=0, select=0):
        """Set the digital upconverter and interpolator configuration.

        :param ch: DAC channel pair (0 or 1)
        :param clr: Keep the phase accumulator cleared
        :param clr_once: Clear the phase accumulator for one cycle
        :param select: Select the data to send to the DAC (0: DUC data, 1: test
            data)
        """
        self.write8(PHASER_ADDR_DUC0_CFG + (ch << 4),
                    (clr << 0) | (clr_once << 1) | (select << 2))

    @kernel
    def set_duc_frequency_mu(self, ch, ftw):
        """Set the DUC frequency.

        :param ch: DAC channel pair (0 or 1)
        :param ftw: DUC frequency tuning word
        """
        self.write32(PHASER_ADDR_DUC0_F + (ch << 4), ftw)

    @kernel
    def set_duc_phase_mu(self, ch, pow):
        """Set the DUC phase offset

        :param ch: DAC channel pair (0 or 1)
        :param pow: DUC phase offset word
        """
        self.write16(PHASER_ADDR_DUC0_P + (ch << 4), pow)

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
        self.write8(PHASER_ADDR_SPI_SEL, select)
        self.write8(PHASER_ADDR_SPI_DIVLEN, (div - 2 >> 3) | (length - 1 << 5))
        self.write8(PHASER_ADDR_SPI_CFG,
                    (offline << 0) | (end << 1) | (clk_phase << 2) |
                    (clk_polarity << 3) | (half_duplex << 4) |
                    (lsb_first << 5))

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
        div = 32  # 100 ns min period
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
    def dac_read(self, addr, div=32) -> TInt32:
        """Read from a DAC register.

        :param addr: Register address to read from
        :param div: SPI clock divider. Needs to be at least 250 to read the
            temperature register.
        """
        t_xfer = self.core.seconds_to_mu((8 + 1)*div*4*ns)
        self.spi_cfg(select=PHASER_SEL_DAC, div=div, end=0)
        self.spi_write(addr | 0x80)
        delay_mu(t_xfer)
        self.spi_write(0)
        delay_mu(t_xfer)
        data = self.spi_read() << 8
        delay(10*us)  # slack
        self.spi_cfg(select=PHASER_SEL_DAC, div=div, end=1)
        self.spi_write(0)
        delay_mu(t_xfer)
        data |= self.spi_read()
        return data

    @kernel
    def att_write(self, ch, data):
        """Set channel attenuation.

        :param ch: RF channel (0 or 1)
        :param data: Attenuator data
        """
        div = 32  # 30 ns min period
        t_xfer = self.core.seconds_to_mu((8 + 1)*div*4*ns)
        self.spi_cfg(select=PHASER_SEL_ATT0 << ch, div=div, end=1)
        self.spi_write(data)
        delay_mu(t_xfer)

    @kernel
    def att_read(self, ch) -> TInt32:
        """Read current attenuation.

        The current attenuation value is read without side effects.

        :param ch: RF channel (0 or 1)
        :return: Current attenuation
        """
        div = 32
        t_xfer = self.core.seconds_to_mu((8 + 1)*div*4*ns)
        self.spi_cfg(select=PHASER_SEL_ATT0 << ch, div=div, end=0)
        self.spi_write(0)
        delay_mu(t_xfer)
        data = self.spi_read()
        delay(10*us)  # slack
        self.spi_cfg(select=PHASER_SEL_ATT0 << ch, div=div, end=1)
        self.spi_write(data)
        delay_mu(t_xfer)
        return data

    @kernel
    def trf_write(self, ch, data, readback=False):
        """Write 32 bits to a TRF upconverter.

        :param ch: RF channel (0 or 1)
        :param data: Register data (32 bit)
        :param readback: Whether to return the read back MISO data
        """
        div = 32  # 50 ns min period
        t_xfer = self.core.seconds_to_mu((8 + 1)*div*4*ns)
        read = 0
        end = 0
        clk_phase = 0
        if readback:
            clk_phase = 1
        for i in range(4):
            if i == 0 or i == 3:
                if i == 3:
                    end = 1
                self.spi_cfg(select=PHASER_SEL_TRF0 << ch, div=div,
                             lsb_first=1, clk_phase=clk_phase, end=end)
            self.spi_write(data)
            data >>= 8
            delay_mu(t_xfer)
            if readback:
                read >>= 8
                read |= self.spi_read() << 24
                delay(10*us)  # slack
        return read

    @kernel
    def trf_read(self, ch, addr, cnt_mux_sel=0) -> TInt32:
        """TRF upconverter register read.

        :param ch: RF channel (0 or 1)
        :param addr: Register address to read
        :param cnt_mux_sel: Report VCO counter min frequency
            or max frequency
        :return: Register data (32 bit)
        """
        self.trf_write(ch, 0x80000008 | (addr << 28) | (cnt_mux_sel << 27))
        # single clk pulse with ~LE to start readback
        self.spi_cfg(select=0, div=32, end=1, length=1)
        self.spi_write(0)
        delay((1 + 1)*32*4*ns)
        return self.trf_write(ch, 0x00000008, readback=True)

    @kernel
    def set_frequency_mu(self, ch, osc, ftw):
        """Set Phaser MultiDDS frequency tuning word.

        :param ch: RF channel (0 or 1)
        :param osc: Oscillator number (0 to 4)
        :param ftw: Frequency tuning word (32 bit)
        """
        addr = ((self.channel_base + 1 + ch) << 8) | (osc << 1)
        rtio_output(addr, ftw)

    @kernel
    def set_amplitude_phase_mu(self, ch, osc, asf=0x7fff, pow=0, clr=0):
        """Set Phaser MultiDDS amplitude, phase offset and accumulator clear.

        :param ch: RF channel (0 or 1)
        :param osc: Oscillator number (0 to 4)
        :param asf: Amplitude (15 bit)
        :param pow: Phase offset word (16 bit)
        :param clr: Clear the phase accumulator (persistent)
        """
        addr = ((self.channel_base + 1 + ch) << 8) | (osc << 1) | 1
        data = (asf & 0x7fff) | (clr << 15) | (pow << 16)
        rtio_output(addr, data)
