"""RTIO driver for the Analog Devices ADF[45]35[56] family of GHz PLLs
on Mirny-style prefixed SPI buses.
"""

# https://github.com/analogdevicesinc/linux/blob/master/Documentation/devicetree/bindings/iio/frequency/adf5355.txt
# https://github.com/analogdevicesinc/linux/blob/master/drivers/iio/frequency/adf5355.c
# https://www.analog.com/media/en/technical-documentation/data-sheets/ADF5355.pdf
# https://www.analog.com/media/en/technical-documentation/data-sheets/ADF5355.pdf
# https://www.analog.com/media/en/technical-documentation/user-guides/EV-ADF5355SD1Z-UG-1087.pdf


from artiq.language.core import kernel, portable, delay
from artiq.language.units import us, GHz, MHz
from artiq.language.types import TInt32, TInt64
from artiq.coredevice import spi2 as spi
from artiq.coredevice.adf5356_reg import *

from numpy import int32, int64, floor, ceil


SPI_CONFIG = (
    0 * spi.SPI_OFFLINE
    | 0 * spi.SPI_END
    | 0 * spi.SPI_INPUT
    | 1 * spi.SPI_CS_POLARITY
    | 0 * spi.SPI_CLK_POLARITY
    | 0 * spi.SPI_CLK_PHASE
    | 0 * spi.SPI_LSB_FIRST
    | 0 * spi.SPI_HALF_DUPLEX
)


ADF5356_MIN_VCO_FREQ = int64(3.4 * GHz)
ADF5356_MAX_VCO_FREQ = int64(6.8 * GHz)
ADF5356_MAX_FREQ_PFD = int32(125.0 * MHz)
ADF5356_MODULUS1 = int32(1 << 24)
ADF5356_MAX_MODULUS2 = int32(1 << 28)  # FIXME: ADF5356 has 28 bits MOD2
ADF5356_MAX_R_CNT = int32(1023)


class ADF5356:
    """Analog Devices AD[45]35[56] family of GHz PLLs.

    :param cpld_device: Mirny CPLD device name
    :param sw_device: Mirny RF switch device name
    :param channel: Mirny RF channel index
    :param ref_doubler: enable/disable reference clock doubler
    :param ref_divider: enable/disable reference clock divide-by-2
    :param core_device: Core device name (default: "core")
    """

    kernel_invariants = {"cpld", "sw", "channel", "core", "sysclk"}

    def __init__(
        self,
        dmgr,
        cpld_device,
        sw_device,
        channel,
        ref_doubler=False,
        ref_divider=False,
        core="core",
    ):
        self.cpld = dmgr.get(cpld_device)
        self.sw = dmgr.get(sw_device)
        self.channel = channel
        self.core = dmgr.get(core)

        self.ref_doubler = ref_doubler
        self.ref_divider = ref_divider
        self.sysclk = self.cpld.refclk
        assert 10 <= self.sysclk / 1e6 <= 600

        self._init_registers()

    @kernel
    def init(self, blind=False):
        """
        Initialize and configure the PLL.

        :param blind: Do not attempt to verify presence.
        """
        if not blind:
            # MUXOUT = VDD
            self.regs[4] = ADF5356_REG4_MUXOUT_UPDATE(self.regs[4], 1)
            self.sync()
            delay(1000 * us)
            if not self.read_muxout():
                raise ValueError("MUXOUT not high")
            delay(800 * us)

            # MUXOUT = DGND
            self.regs[4] = ADF5356_REG4_MUXOUT_UPDATE(self.regs[4], 2)
            self.sync()
            delay(1000 * us)
            if self.read_muxout():
                raise ValueError("MUXOUT not low")
            delay(800 * us)

            # MUXOUT = digital lock-detect
            self.regs[4] = ADF5356_REG4_MUXOUT_UPDATE(self.regs[4], 6)
        else:
            self.sync()

    @kernel
    def set_att(self, att):
        """Set digital step attenuator in SI units.

        This method will write the attenuator settings of the channel.

        .. seealso:: :meth:`artiq.coredevice.mirny.Mirny.set_att`

        :param att: Attenuation in dB.
        """
        self.cpld.set_att(self.channel, att)

    @kernel
    def set_att_mu(self, att):
        """Set digital step attenuator in machine units.

        :param att: Attenuation setting, 8 bit digital.
        """
        self.cpld.set_att_mu(self.channel, att)

    @kernel
    def write(self, data):
        self.cpld.write_ext(self.channel | 4, 32, data)

    @kernel
    def read_muxout(self):
        """
        Read the state of the MUXOUT line.

        By default, this is configured to be the digital lock detection.
        """
        return bool(self.cpld.read_reg(0) & (1 << (self.channel + 8)))

    @kernel
    def set_output_power_mu(self, n):
        """
        Set the power level at output A of the PLL chip in machine units.

        This driver defaults to `n = 3` at init.

        :param n: output power setting, 0, 1, 2, or 3 (see ADF5356 datasheet, fig. 44).
        """
        if n not in [0, 1, 2, 3]:
            raise ValueError("invalid power setting")
        self.regs[6] = ADF5356_REG6_RF_OUTPUT_A_POWER_UPDATE(self.regs[6], n)
        self.sync()

    @portable
    def output_power_mu(self):
        """
        Return the power level at output A of the PLL chip in machine units.
        """
        return ADF5356_REG6_RF_OUTPUT_A_POWER_GET(self.regs[6])

    @kernel
    def enable_output(self):
        """
        Enable output A of the PLL chip. This is the default after init.
        """
        self.regs[6] |= ADF5356_REG6_RF_OUTPUT_A_ENABLE(1)
        self.sync()

    @kernel
    def disable_output(self):
        """
        Disable output A of the PLL chip.
        """
        self.regs[6] &= ~ADF5356_REG6_RF_OUTPUT_A_ENABLE(1)
        self.sync()

    @kernel
    def set_frequency(self, f):
        """
        Output given frequency on output A.

        :param f: 53.125 MHz <= f <= 6800 MHz
        """
        freq = int64(round(f))

        if freq > ADF5356_MAX_VCO_FREQ:
            raise ValueError("Requested too high frequency")

        # select minimal output divider
        rf_div_sel = 0
        while freq < ADF5356_MIN_VCO_FREQ:
            freq <<= 1
            rf_div_sel += 1

        if (1 << rf_div_sel) > 64:
            raise ValueError("Requested too low frequency")

        # choose reference divider that maximizes PFD frequency
        self.regs[4] = ADF5356_REG4_R_COUNTER_UPDATE(
            self.regs[4], self._compute_reference_counter()
        )
        f_pfd = self.f_pfd()

        # choose prescaler
        if freq > int64(6e9):
            self.regs[0] |= ADF5356_REG0_PRESCALER(1)  # 8/9
            n_min, n_max = 75, 65535

            # adjust reference divider to be able to match n_min constraint
            while n_min * f_pfd > freq:
                r = ADF5356_REG4_R_COUNTER_GET(self.regs[4])
                self.regs[4] = ADF5356_REG4_R_COUNTER_UPDATE(self.regs[4], r + 1)
                f_pfd = self.f_pfd()
        else:
            self.regs[0] &= ~ADF5356_REG0_PRESCALER(1)  # 4/5
            n_min, n_max = 23, 32767

        # calculate PLL parameters
        n, frac1, (frac2_msb, frac2_lsb), (mod2_msb, mod2_lsb) = calculate_pll(
            freq, f_pfd
        )

        if not (n_min <= n <= n_max):
            raise ValueError("Invalid INT value")

        # configure PLL
        self.regs[0] = ADF5356_REG0_INT_VALUE_UPDATE(self.regs[0], n)
        self.regs[1] = ADF5356_REG1_MAIN_FRAC_VALUE_UPDATE(self.regs[1], frac1)
        self.regs[2] = ADF5356_REG2_AUX_FRAC_LSB_VALUE_UPDATE(self.regs[2], frac2_lsb)
        self.regs[2] = ADF5356_REG2_AUX_MOD_LSB_VALUE_UPDATE(self.regs[2], mod2_lsb)
        self.regs[13] = ADF5356_REG13_AUX_FRAC_MSB_VALUE_UPDATE(
            self.regs[13], frac2_msb
        )
        self.regs[13] = ADF5356_REG13_AUX_MOD_MSB_VALUE_UPDATE(self.regs[13], mod2_msb)

        self.regs[6] = ADF5356_REG6_RF_DIVIDER_SELECT_UPDATE(self.regs[6], rf_div_sel)
        self.regs[6] = ADF5356_REG6_CP_BLEED_CURRENT_UPDATE(
            self.regs[6], int32(floor(24 * f_pfd / (61.44 * MHz)))
        )
        self.regs[9] = ADF5356_REG9_VCO_BAND_DIVISION_UPDATE(
            self.regs[9], int32(ceil(f_pfd / 160e3))
        )

        # commit
        self.sync()

    @kernel
    def sync(self):
        """
        Write all registers to the device. Attempts to lock the PLL.
        """
        f_pfd = self.f_pfd()
        delay(200 * us)         # Slack

        if f_pfd <= 75.0 * MHz:
            for i in range(13, 0, -1):
                self.write(self.regs[i])
            delay(200 * us)
            self.write(self.regs[0] | ADF5356_REG0_AUTOCAL(1))
        else:
            # AUTOCAL AT HALF PFD FREQUENCY

            # calculate PLL at f_pfd/2
            n, frac1, (frac2_msb, frac2_lsb), (mod2_msb, mod2_lsb) = calculate_pll(
                self.f_vco(), f_pfd >> 1
            )
            delay(200 * us)     # Slack

            self.write(
                13
                | ADF5356_REG13_AUX_FRAC_MSB_VALUE(frac2_msb)
                | ADF5356_REG13_AUX_MOD_MSB_VALUE(mod2_msb)
            )

            for i in range(12, 4, -1):
                self.write(self.regs[i])

            self.write(
                ADF5356_REG4_R_COUNTER_UPDATE(self.regs[4], 2 * self.ref_counter())
            )

            self.write(self.regs[3])
            self.write(
                2
                | ADF5356_REG2_AUX_MOD_LSB_VALUE(mod2_lsb)
                | ADF5356_REG2_AUX_FRAC_LSB_VALUE(frac2_lsb)
            )
            self.write(1 | ADF5356_REG1_MAIN_FRAC_VALUE(frac1))

            delay(200 * us)
            self.write(ADF5356_REG0_INT_VALUE(n) | ADF5356_REG0_AUTOCAL(1))

            # RELOCK AT WANTED PFD FREQUENCY

            for i in [4, 2, 1]:
                self.write(self.regs[i])

            # force-disable autocal
            self.write(self.regs[0] & ~ADF5356_REG0_AUTOCAL(1))

    @portable
    def f_pfd(self) -> TInt64:
        """
        Return the PFD frequency for the cached set of registers.
        """
        r = ADF5356_REG4_R_COUNTER_GET(self.regs[4])
        d = ADF5356_REG4_R_DOUBLER_GET(self.regs[4])
        t = ADF5356_REG4_R_DIVIDER_GET(self.regs[4])
        return self._compute_pfd_frequency(r, d, t)

    @portable
    def f_vco(self) -> TInt64:
        """
        Return the VCO frequency for the cached set of registers.
        """
        return int64(
            self.f_pfd()
            * (
                self.pll_n()
                + (self.pll_frac1() + self.pll_frac2() / self.pll_mod2())
                / ADF5356_MODULUS1
            )
        )

    @portable
    def pll_n(self) -> TInt32:
        """
        Return the PLL integer value (INT) for the cached set of registers.
        """
        return ADF5356_REG0_INT_VALUE_GET(self.regs[0])

    @portable
    def pll_frac1(self) -> TInt32:
        """
        Return the main fractional value (FRAC1) for the cached set of registers.
        """
        return ADF5356_REG1_MAIN_FRAC_VALUE_GET(self.regs[1])

    @portable
    def pll_frac2(self) -> TInt32:
        """
        Return the auxiliary fractional value (FRAC2) for the cached set of registers.
        """
        return (
            ADF5356_REG13_AUX_FRAC_MSB_VALUE_GET(self.regs[13]) << 14
        ) | ADF5356_REG2_AUX_FRAC_LSB_VALUE_GET(self.regs[2])

    @portable
    def pll_mod2(self) -> TInt32:
        """
        Return the auxiliary modulus value (MOD2) for the cached set of registers.
        """
        return (
            ADF5356_REG13_AUX_MOD_MSB_VALUE_GET(self.regs[13]) << 14
        ) | ADF5356_REG2_AUX_MOD_LSB_VALUE_GET(self.regs[2])

    @portable
    def ref_counter(self) -> TInt32:
        """
        Return the reference counter value (R) for the cached set of registers.
        """
        return ADF5356_REG4_R_COUNTER_GET(self.regs[4])

    @portable
    def output_divider(self) -> TInt32:
        """
        Return the value of the output A divider.
        """
        return 1 << ADF5356_REG6_RF_DIVIDER_SELECT_GET(self.regs[6])

    def info(self):
        """
        Return a summary of high-level parameters as a dict.
        """
        prescaler = ADF5356_REG0_PRESCALER_GET(self.regs[0])
        return {
            # output
            "f_outA": self.f_vco() / self.output_divider(),
            "f_outB": self.f_vco() * 2,
            "output_divider": self.output_divider(),
            # PLL parameters
            "f_vco": self.f_vco(),
            "pll_n": self.pll_n(),
            "pll_frac1": self.pll_frac1(),
            "pll_frac2": self.pll_frac2(),
            "pll_mod2": self.pll_mod2(),
            "prescaler": "4/5" if prescaler == 0 else "8/9",
            # reference / PFD
            "sysclk": self.sysclk,
            "ref_doubler": self.ref_doubler,
            "ref_divider": self.ref_divider,
            "ref_counter": self.ref_counter(),
            "f_pfd": self.f_pfd(),
        }

    @portable
    def _init_registers(self):
        """
        Initialize cached registers with sensible defaults.
        """
        # fill with control bits
        self.regs = [int32(i) for i in range(ADF5356_NUM_REGS)]

        # REG2
        # ====

        # avoid divide-by-zero
        self.regs[2] |= ADF5356_REG2_AUX_MOD_LSB_VALUE(1)

        # REG4
        # ====

        # single-ended reference mode is recommended
        # for references up to 250 MHz, even if the signal is differential
        if self.sysclk <= 250 * MHz:
            self.regs[4] |= ADF5356_REG4_REF_MODE(0)
        else:
            self.regs[4] |= ADF5356_REG4_REF_MODE(1)

        # phase detector polarity: positive
        self.regs[4] |= ADF5356_REG4_PD_POLARITY(1)

        # charge pump current: 0.94 mA
        self.regs[4] |= ADF5356_REG4_CURRENT_SETTING(2)

        # MUXOUT: digital lock detect
        self.regs[4] |= ADF5356_REG4_MUX_LOGIC(1)  # 3v3 logic
        self.regs[4] |= ADF5356_REG4_MUXOUT(6)

        # setup reference path
        if self.ref_doubler:
            self.regs[4] |= ADF5356_REG4_R_DOUBLER(1)

        if self.ref_divider:
            self.regs[4] |= ADF5356_REG4_R_DIVIDER(1)

        r = self._compute_reference_counter()
        self.regs[4] |= ADF5356_REG4_R_COUNTER(r)

        # REG5
        # ====

        # reserved values
        self.regs[5] = int32(0x800025)

        # REG6
        # ====

        # reserved values
        self.regs[6] = int32(0x14000006)

        # enable negative bleed
        self.regs[6] |= ADF5356_REG6_NEGATIVE_BLEED(1)

        # charge pump bleed current
        self.regs[6] |= ADF5356_REG6_CP_BLEED_CURRENT(
            int32(floor(24 * self.f_pfd() / (61.44 * MHz)))
        )

        # direct feedback from VCO to N counter
        self.regs[6] |= ADF5356_REG6_FB_SELECT(1)

        # mute until the PLL is locked
        self.regs[6] |= ADF5356_REG6_MUTE_TILL_LD(1)

        # enable output A
        self.regs[6] |= ADF5356_REG6_RF_OUTPUT_A_ENABLE(1)

        # set output A power to max power, is adjusted by extra attenuator
        self.regs[6] |= ADF5356_REG6_RF_OUTPUT_A_POWER(3)  # +5 dBm

        # REG7
        # ====

        # reserved values
        self.regs[7] = int32(0x10000007)

        # sync load-enable to reference
        self.regs[7] |= ADF5356_REG7_LE_SYNC(1)

        # frac-N lock-detect precision: 12 ns
        self.regs[7] |= ADF5356_REG7_FRAC_N_LD_PRECISION(3)

        # REG8
        # ====

        # reserved values
        self.regs[8] = int32(0x102D0428)

        # REG9
        # ====

        # default timeouts (from eval software)
        self.regs[9] |= (
            ADF5356_REG9_SYNTH_LOCK_TIMEOUT(13)
            | ADF5356_REG9_AUTOCAL_TIMEOUT(31)
            | ADF5356_REG9_TIMEOUT(0x67)
        )

        self.regs[9] |= ADF5356_REG9_VCO_BAND_DIVISION(
            int32(ceil(self.f_pfd() / 160e3))
        )

        # REG10
        # =====

        # reserved values
        self.regs[10] = int32(0xC0000A)

        # ADC defaults (from eval software)
        self.regs[10] |= (
            ADF5356_REG10_ADC_ENABLE(1)
            | ADF5356_REG10_ADC_CLK_DIV(256)
            | ADF5356_REG10_ADC_CONV(1)
        )

        # REG11
        # =====

        # reserved values
        self.regs[11] = int32(0x61200B)

        # REG12
        # =====

        # reserved values
        self.regs[12] = int32(0x15FC)

    @portable
    def _compute_pfd_frequency(self, r, d, t) -> TInt64:
        """
        Calculate the PFD frequency from the given reference path parameters
        """
        return int64(self.sysclk * ((1 + d) / (r * (1 + t))))

    @portable
    def _compute_reference_counter(self) -> TInt32:
        """
        Determine the reference counter R that maximizes the PFD frequency
        """
        d = ADF5356_REG4_R_DOUBLER_GET(self.regs[4])
        t = ADF5356_REG4_R_DIVIDER_GET(self.regs[4])
        r = 1
        while self._compute_pfd_frequency(r, d, t) > ADF5356_MAX_FREQ_PFD:
            r += 1
        return int32(r)


@portable
def gcd(a, b):
    while b:
        a, b = b, a % b
    return a


@portable
def split_msb_lsb_28b(v):
    return int32((v >> 14) & 0x3FFF), int32(v & 0x3FFF)


@portable
def calculate_pll(f_vco: TInt64, f_pfd: TInt64):
    """
    Calculate fractional-N PLL parameters such that

    ``f_vco`` = ``f_pfd`` * (``n`` + (``frac1`` + ``frac2``/``mod2``) / ``mod1``)

    where
        ``mod1 = 2**24`` and ``mod2 <= 2**28``

    :param f_vco: target VCO frequency
    :param f_pfd: PFD frequency
    :return: ``(n, frac1, (frac2_msb, frac2_lsb), (mod2_msb, mod2_lsb))``
    """
    f_pfd = int64(f_pfd)
    f_vco = int64(f_vco)

    # integral part
    n, r = int32(f_vco // f_pfd), f_vco % f_pfd

    # main fractional part
    r *= ADF5356_MODULUS1
    frac1, frac2 = int32(r // f_pfd), r % f_pfd

    # auxiliary fractional part
    mod2 = f_pfd

    while mod2 > ADF5356_MAX_MODULUS2:
        mod2 >>= 1
        frac2 >>= 1

    gcd_div = gcd(frac2, mod2)
    mod2 //= gcd_div
    frac2 //= gcd_div

    return n, frac1, split_msb_lsb_28b(frac2), split_msb_lsb_28b(mod2)
