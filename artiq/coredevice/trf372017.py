from numpy import int32, int64

from artiq.coredevice import spi2 as spi
from artiq.coredevice.trf372017_reg import TRF372017 as TRF372017Reg
from artiq.language.core import *
from artiq.language.types import *
from artiq.language.units import us, GHz, MHz

TRF_MAX_MIXER_FREQ = 4.8 * GHz
TRF_MIN_MIXER_FREQ = 300 * MHz
TRF_MIN_VCO_FREQ = 2.4 * GHz
TRF_MAX_N_FREQ = 375 * MHz
TRF_MAX_PM_FREQ = 3 * GHz
TRF_MAX_PFD_FREQ = 100 * MHz
TRF_MAX_CAL_FREQ = 1 * MHz

TRF_SPI_DIV = 10  # min 50 ns - SLWS224E Section 6.5
TRF_SPI_CONFIG = (
    0 * spi.SPI_OFFLINE
    | 0 * spi.SPI_END
    | 0 * spi.SPI_INPUT
    | 0 * spi.SPI_CS_POLARITY
    | 0 * spi.SPI_CLK_POLARITY
    | 0 * spi.SPI_CLK_PHASE
    | 1 * spi.SPI_LSB_FIRST
    | 0 * spi.SPI_HALF_DUPLEX
)


@portable
def calculate_pll(
    f_refclk: TFloat, f_mixer: TFloat
) -> TTuple([TInt32, TInt32, TInt32, TInt32, TInt32, TInt32]):
    """Calculate fractional PLL parameters with the best phase noise performance

    ``f_rf = (1 / tx_div_sel) * (f_refclk / r_div) * pll_div_sel * (n_int + n_frac / 2**25)``

    :param f_refclk: Reference clock frequency in Hz
    :param f_mixer: Mixer frequency in Hz (300 MHz - 4800 MHz)
    :return: (``r_div``, ``pres_sel``, ``n_int``, ``n_frac``, ``pll_div_sel``, ``tx_div_sel``)
    """
    if f_mixer > TRF_MAX_MIXER_FREQ or f_mixer < TRF_MIN_MIXER_FREQ:
        raise ValueError("Requested frequency out of range")

    tx_div_sel = 0
    f_vco = f_mixer
    while f_vco < TRF_MIN_VCO_FREQ:
        f_vco *= 2
        tx_div_sel += 1

    # SLWS224E Section 7.3.2.1 c prescaler settings :
    # - 23 <= NINT < 75 when prescaler = 4/5
    # - 75 <= NINT < 2**16 when prescaler = 8/9
    for n_min, n_max, prescaler in [(23, 75, 4), (75, 1 << 16, 8)]:
        # To have the best phaser noise performance. The f_pfd need to run as high as possible - SLWS224E Section 7.3.2.1 b
        # And a PLL config with the highest possible f_pm will have the higest f_pfd. As f_pfd = f_vco / (pll_div * n) = f_pm / n.
        pres_sel = 0 if prescaler == 4 else 1
        pll_div_sel = 0
        f_pm = f_vco
        while (f_pm / prescaler) > TRF_MAX_N_FREQ or f_pm > TRF_MAX_PM_FREQ:
            f_pm /= 2
            pll_div_sel += 1

        r_div = 1
        f_pfd = f_refclk
        n_int, n_frac = calculate_n_divider(f_pm, f_pfd)
        while n_int < n_min or f_pfd > TRF_MAX_PFD_FREQ:
            r_div += 1
            f_pfd = f_refclk / r_div
            n_int, n_frac = calculate_n_divider(f_pm, f_pfd)

        if n_int < n_max:
            return r_div, pres_sel, n_int, n_frac, pll_div_sel, tx_div_sel
    raise ValueError("Cannot find a PLL parameter that fits the requirement")


@portable
def calculate_n_divider(f_pm, f_pfd) -> TTuple([TInt32, TInt32]):
    """Calculate fractional PLL parameters such that

    ``f_pm = f_pfd * (n_int + n_frac/2**25)``

    :param f_pm: Prescaler frequency
    :param f_pfd: Phase frequency detector frequency
    :return: (``n_int``, ``n_frac``)
    """
    return int32(f_pm // f_pfd), int32(((f_pm / f_pfd) % 1.0) * float(1 << 25))


@portable
def calculate_cal_clk_sel(f_refclk, r_div) -> TInt32:
    """Calculate and return cal_clk_sel, the 4-bit VCO calibration clock factor.

    :param f_refclk: Reference clock frequency in Hz
    :param r_div: 13-bit reference divider
    :return: ``cal_clk_sel``
    """
    f_pfd = f_refclk / r_div
    cal_clk_sel = 0b1000  # x1
    if f_pfd <= TRF_MAX_CAL_FREQ:
        return cal_clk_sel
    else:
        f_cal = f_pfd
        while f_cal > TRF_MAX_CAL_FREQ:
            f_cal /= 2
            cal_clk_sel += 1
    return cal_clk_sel


class TRF372017:
    """IQ Upconverter TRF372017 driver

    :param spi_device: SPI bus device name.
    :param refclk: Reference clock frequency in Hz
    :param use_external_lo: Bypass internal PLL and use external LO directly when set to True.
    :param core_device: Core device name (default: "core").
    """

    kernel_invariants = {"core", "bus", "refclk", "use_external_lo", "init_mmap"}

    def __init__(self, dmgr, spi_device, refclk, use_external_lo, core_device="core"):
        self.core = dmgr.get(core_device)
        self.bus = dmgr.get(spi_device)

        self.refclk = refclk

        self.use_external_lo = use_external_lo
        if self.use_external_lo:
            settings = {
                # Select the external LO instead of internal VCO - SLWS224E Section 7.3.5
                "en_extvco": 0b1,
            }
        else:
            settings = {
                # Fractional mode setup - SLWS224E Section 7.3.3
                "en_frac": 0b1,
                "en_isource": 0b1,
                "en_dith": 0b1,
                "mod_ord": 0b10,
                "dith_sel": 0b0,
                "del_sd_clk": 0b10,
                "en_ld_isource": 0b0,
                "isource_sink": 0b0,
                "isource_trim": 0b100,
                # Lock detect for fractional mode - SLWS224E Section 7.3.3
                "ld_ana_prec": 0b11,
            }
        self.init_mmap = TRF372017Reg(settings).get_mmap()

        self.vco_calibration_duration_mu = int64(0)

    @kernel
    def init(self):
        """Initialize and configure the upconverter.

        Set the mixer frequency to 2.875 GHz if external LO is not provided
        """
        if self.read(0x00) & 0x60 != 0x60:
            raise ValueError("TRF372017 chip id mismatch")
        delay(40.0 * us)

        for data in self.init_mmap:
            self.write(data)

        if self.use_external_lo:
            # pass the LO output to downstream upconverter
            self.enable_lo_output(True)
        else:
            self.enable_mixer_rf_output(False)
            self.set_mixer_frequency(2.875 * GHz)
            self.enable_mixer_rf_output(True)

    @kernel
    def read(self, addr) -> TInt32:
        # Write to register 0
        self.bus.set_config_mu(
            TRF_SPI_CONFIG | spi.SPI_END,
            32,
            TRF_SPI_DIV,
            1,
        )
        self.bus.write(0x80000008 | (addr & 0b111) << 28)

        # Hold CS high for one cycle
        self.bus.set_config_mu(
            TRF_SPI_CONFIG | spi.SPI_END,
            1,
            TRF_SPI_DIV,
            0,
        )
        self.bus.write(0)

        # Read back
        self.bus.set_config_mu(
            TRF_SPI_CONFIG | spi.SPI_END | spi.SPI_INPUT | spi.SPI_CLK_PHASE,
            32,
            TRF_SPI_DIV,
            1,
        )
        self.bus.write(0)
        return self.bus.read()

    @kernel
    def write(self, data):
        self.bus.set_config_mu(
            TRF_SPI_CONFIG | spi.SPI_END,
            32,
            TRF_SPI_DIV,
            1,
        )
        self.bus.write(data)

    @kernel
    def calibrate_vco(self):
        """Start calibration of the VCO and advance timeline by the VCO calibration duration (:attr:`vco_calibration_duration_mu`).

        .. warning:: RF and LO outputs must be disabled during VCO calibration via :meth:`enable_mixer_rf_output` and :meth:`enable_lo_output`.
        """
        reg_0x02 = self.read(0x02)
        delay(40.0 * us)
        # The bit will reset automatically, no need to write the original value again - SLWS224E Table 16
        self.write(reg_0x02 | (1 << 31))
        delay_mu(self.vco_calibration_duration_mu)

        if self.read(0x00) & 0x1000 == 0x1000:
            raise ValueError("TRF372017 VCO calibration error")
        delay(40.0 * us)

    @kernel
    def enable_mixer_rf_output(self, output_enable):
        """Enable/disable mixer RF output

        :param output_enable: Enable mixer RF output when set to True
        """
        reg_0x04 = self.read(0x04)
        delay(40.0 * us)
        if output_enable:
            reg_0x04 &= ~(1 << 14)
        else:
            # To disable rf output, set PWD_TX_DIV to 0b1 - SLWS224E Section 7.3.11
            reg_0x04 |= 1 << 14
        self.write(reg_0x04)

    @kernel
    def enable_lo_output(self, output_enable):
        """Enable/disable LO output

        :param output_enable: Enable LO output when set to True
        """
        reg_0x04 = self.read(0x04)
        delay(40.0 * us)
        if output_enable:
            reg_0x04 &= ~((1 << 12) | (1 << 13))
        else:
            # To disable lo output, set PWD_OUT_BUFF and PWD_LO_DIV to 0b1 - SLWS224E Section 7.3.11
            reg_0x04 |= (1 << 12) | (1 << 13)
        self.write(reg_0x04)

    @kernel
    def set_mixer_frequency(self, frequency):
        """Calculate PLL parameter, set mixer frequency and calibrate VCO

        .. warning:: Before calling this method, RF and LO outputs must be disabled via :meth:`enable_mixer_rf_output` and :meth:`enable_lo_output` due to VCO calibration.

        :param f_mixer: Mixer frequency in Hz (300 MHz - 4800 MHz)
        """
        r_div, pres_sel, n_int, n_frac, pll_div_sel, tx_div_sel = calculate_pll(
            self.refclk, frequency
        )
        cal_clk_sel = calculate_cal_clk_sel(self.refclk, r_div)
        self.update_vco_calibration_duration_mu(r_div, cal_clk_sel)
        delay(100.0 * us)  # slack

        self.set_cal_clk_sel(cal_clk_sel)
        self.set_pll_registers(r_div, pres_sel, n_int, n_frac, pll_div_sel, tx_div_sel)

        self.calibrate_vco()

    @kernel
    def set_cal_clk_sel(self, cal_clk_sel):
        """Write the 4-bit VCO calibration clock factor register

        :param cal_clk_sel: 4-bit VCO calibration clock factor
        """
        reg_0x01 = self.read(0x01)
        delay(40.0 * us)
        self.write(reg_0x01 & ~(0xF << 27) | cal_clk_sel << 27)

    @kernel
    def set_pll_registers(
        self, r_div, prsc_sel, n_int, n_frac, pll_div_sel, tx_div_sel
    ):
        """Write the PLL parameter to registers.

        :param r_div: 13-bit reference divider
        :param prsc_sel: 1-bit prescaler setting (set to 0 for 4/5 and 1 for 8/9)
        :param n_int: 16-bit fractional PLL integer division factor
        :param n_frac: 25-bit fractional PLL fractionality
        :param n_pll_div_sel: 2-bit PLL divider setting
        :param n_tx_div_sel: 2-bit tx divider
        """
        reg_0x01 = self.read(0x01)
        delay(40.0 * us)
        self.write(reg_0x01 & ~(0x1FFF << 5) | r_div << 5)

        reg_0x02 = self.read(0x02)
        delay(40.0 * us)
        self.write(
            reg_0x02 & ~(0xFFFF << 5 | 0b11 << 21 | 0b1 << 23)
            | n_int << 5
            | pll_div_sel << 21
            | prsc_sel << 23
        )

        reg_0x03 = self.read(0x03)
        delay(40.0 * us)
        self.write(reg_0x03 & ~(0x1FFFFFF << 5) | n_frac << 5)

        reg_0x06 = self.read(0x06)
        delay(40.0 * us)
        self.write(reg_0x06 & ~(0xF << 24) | tx_div_sel << 24)

    @portable
    def update_vco_calibration_duration_mu(self, r_div, cal_clk_sel):
        """Calculate and set the VCO calibration duration (:attr:`vco_calibration_duration_mu`).

        This method updates the VCO calibration duration which is used
        in :meth:`calibrate_vco` to advance the timeline.

        Use this method every time r_div is changed.

        :param r_div: 13-bit reference divider
        :param cal_clk_sel: 4-bit VCO calibration clock factor
        """
        f_pfd = self.refclk / r_div
        # cal_clk_sel is ones' complement
        if cal_clk_sel & 0b1000 == 0b1000:
            f_cal = f_pfd / (1 << (cal_clk_sel & 0b111))
        else:
            f_cal = f_pfd * (1 << (cal_clk_sel ^ 0b111))

        # Max VCO calibration time = 46 cal_clk cycle - SLWS224E Table 3
        self.vco_calibration_duration_mu = self.core.seconds_to_mu(46 / f_cal)
