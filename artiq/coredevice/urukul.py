from artiq.language.core import kernel, delay, portable, at_mu, now_mu
from artiq.language.units import us, ms

from numpy import int32, int64

from artiq.coredevice import spi2 as spi


SPI_CONFIG = (0*spi.SPI_OFFLINE | 0*spi.SPI_END |
              0*spi.SPI_INPUT | 1*spi.SPI_CS_POLARITY |
              0*spi.SPI_CLK_POLARITY | 0*spi.SPI_CLK_PHASE |
              0*spi.SPI_LSB_FIRST | 0*spi.SPI_HALF_DUPLEX)

# SPI clock write and read dividers
SPIT_CFG_WR = 2
SPIT_CFG_RD = 16
# 30 MHz fmax, 20 ns setup, 40 ns shift to latch (limiting)
SPIT_ATT_WR = 6
SPIT_ATT_RD = 16
SPIT_DDS_WR = 2
SPIT_DDS_RD = 16

# CFG configuration register bit offsets
CFG_RF_SW = 0
CFG_LED = 4
CFG_PROFILE = 8
CFG_IO_UPDATE = 12
CFG_MASK_NU = 13
CFG_CLK_SEL0 = 17
CFG_CLK_SEL1 = 21
CFG_SYNC_SEL = 18
CFG_RST = 19
CFG_IO_RST = 20
CFG_CLK_DIV = 22

# STA status register bit offsets
STA_RF_SW = 0
STA_SMP_ERR = 4
STA_PLL_LOCK = 8
STA_IFC_MODE = 12
STA_PROTO_REV = 16

# supported hardware and CPLD code version
STA_PROTO_REV_MATCH = 0x08

# chip select (decoded)
CS_CFG = 1
CS_ATT = 2
CS_DDS_MULTI = 3
CS_DDS_CH0 = 4
CS_DDS_CH1 = 5
CS_DDS_CH2 = 6
CS_DDS_CH3 = 7


@portable
def urukul_cfg(rf_sw, led, profile, io_update, mask_nu,
               clk_sel, sync_sel, rst, io_rst, clk_div):
    """Build Urukul CPLD configuration register"""
    return ((rf_sw << CFG_RF_SW) |
            (led << CFG_LED) |
            (profile << CFG_PROFILE) |
            (io_update << CFG_IO_UPDATE) |
            (mask_nu << CFG_MASK_NU) |
            ((clk_sel & 0x01) << CFG_CLK_SEL0) |
            ((clk_sel & 0x02) << (CFG_CLK_SEL1 - 1)) |
            (sync_sel << CFG_SYNC_SEL) |
            (rst << CFG_RST) |
            (io_rst << CFG_IO_RST) |
            (clk_div << CFG_CLK_DIV))


@portable
def urukul_sta_rf_sw(sta):
    """Return the RF switch status from Urukul status register value."""
    return (sta >> STA_RF_SW) & 0xf


@portable
def urukul_sta_smp_err(sta):
    """Return the SMP_ERR status from Urukul status register value."""
    return (sta >> STA_SMP_ERR) & 0xf


@portable
def urukul_sta_pll_lock(sta):
    """Return the PLL_LOCK status from Urukul status register value."""
    return (sta >> STA_PLL_LOCK) & 0xf


@portable
def urukul_sta_ifc_mode(sta):
    """Return the IFC_MODE status from Urukul status register value."""
    return (sta >> STA_IFC_MODE) & 0xf


@portable
def urukul_sta_proto_rev(sta):
    """Return the PROTO_REV value from Urukul status register value."""
    return (sta >> STA_PROTO_REV) & 0x7f


class _RegIOUpdate:
    def __init__(self, cpld):
        self.cpld = cpld

    @kernel
    def pulse(self, t):
        cfg = self.cpld.cfg_reg
        self.cpld.cfg_write(cfg | (1 << CFG_IO_UPDATE))
        delay(t)
        self.cpld.cfg_write(cfg)


class _DummySync:
    def __init__(self, cpld):
        self.cpld = cpld

    @kernel
    def set_mu(self, ftw):
        pass


class CPLD:
    """Urukul CPLD SPI router and configuration interface.

    :param spi_device: SPI bus device name
    :param io_update_device: IO update RTIO TTLOut channel name
    :param dds_reset_device: DDS reset RTIO TTLOut channel name
    :param sync_device: AD9910 SYNC_IN RTIO TTLClockGen channel name
    :param refclk: Reference clock (SMA, MMCX or on-board 100 MHz oscillator)
        frequency in Hz
    :param clk_sel: Reference clock selection. For hardware revision >= 1.3
        valid options are: 0 - internal 100MHz XO; 1 - front-panel SMA; 2
        internal MMCX. For hardware revision <= v1.2 valid options are: 0 -
        either XO or MMCX dependent on component population; 1 SMA. Unsupported
        clocking options are silently ignored.
    :param clk_div: Reference clock divider. Valid options are 0: variant
        dependent default (divide-by-4 for AD9910 and divide-by-1 for AD9912);
        1: divide-by-1; 2: divide-by-2; 3: divide-by-4.
        On Urukul boards with CPLD gateware before v1.3.1 only the default
        (0, i.e. variant dependent divider) is valid.
    :param sync_sel: SYNC (multi-chip synchronisation) signal source selection.
        0 corresponds to SYNC_IN being supplied by the FPGA via the EEM
        connector. 1 corresponds to SYNC_OUT from DDS0 being distributed to the
        other chips.
    :param rf_sw: Initial CPLD RF switch register setting (default: 0x0).
        Knowledge of this state is not transferred between experiments.
    :param att: Initial attenuator setting shift register (default:
        0x00000000). See also :meth:`get_att_mu` which retrieves the hardware
        state without side effects. Knowledge of this state is not transferred
        between experiments.
    :param sync_div: SYNC_IN generator divider. The ratio between the coarse
        RTIO frequency and the SYNC_IN generator frequency (default: 2 if
        `sync_device` was specified).
    :param core_device: Core device name

    If the clocking is incorrect (for example, setting ``clk_sel`` to the
    front panel SMA with no clock connected), then the ``init()`` method of
    the DDS channels can fail with the error message ``PLL lock timeout``.
    """
    kernel_invariants = {"refclk", "bus", "core", "io_update", "clk_div"}

    def __init__(self, dmgr, spi_device, io_update_device=None,
                 dds_reset_device=None, sync_device=None,
                 sync_sel=0, clk_sel=0, clk_div=0, rf_sw=0,
                 refclk=125e6, att=0x00000000, sync_div=None,
                 core_device="core"):

        self.core = dmgr.get(core_device)
        self.refclk = refclk
        assert 0 <= clk_div <= 3
        self.clk_div = clk_div

        self.bus = dmgr.get(spi_device)
        if io_update_device is not None:
            self.io_update = dmgr.get(io_update_device)
        else:
            self.io_update = _RegIOUpdate(self)
        if dds_reset_device is not None:
            self.dds_reset = dmgr.get(dds_reset_device)
        if sync_device is not None:
            self.sync = dmgr.get(sync_device)
            if sync_div is None:
                sync_div = 2
        else:
            self.sync = _DummySync(self)
            assert sync_div is None
            sync_div = 0

        self.cfg_reg = urukul_cfg(rf_sw=rf_sw, led=0, profile=0,
                                  io_update=0, mask_nu=0, clk_sel=clk_sel,
                                  sync_sel=sync_sel,
                                  rst=0, io_rst=0, clk_div=clk_div)
        self.att_reg = int32(int64(att))
        self.sync_div = sync_div

    @kernel
    def cfg_write(self, cfg):
        """Write to the configuration register.

        See :func:`urukul_cfg` for possible flags.

        :param data: 24 bit data to be written. Will be stored at
            :attr:`cfg_reg`.
        """
        self.bus.set_config_mu(SPI_CONFIG | spi.SPI_END, 24,
                               SPIT_CFG_WR, CS_CFG)
        self.bus.write(cfg << 8)
        self.cfg_reg = cfg

    @kernel
    def sta_read(self):
        """Read the status register.

        Use any of the following functions to extract values:

            * :func:`urukul_sta_rf_sw`
            * :func:`urukul_sta_smp_err`
            * :func:`urukul_sta_pll_lock`
            * :func:`urukul_sta_ifc_mode`
            * :func:`urukul_sta_proto_rev`

        :return: The status register value.
        """
        self.bus.set_config_mu(SPI_CONFIG | spi.SPI_END | spi.SPI_INPUT, 24,
                               SPIT_CFG_RD, CS_CFG)
        self.bus.write(self.cfg_reg << 8)
        return self.bus.read()

    @kernel
    def init(self, blind=False):
        """Initialize and detect Urukul.

        Resets the DDS I/O interface and verifies correct CPLD gateware
        version.
        Does not pulse the DDS MASTER_RESET as that confuses the AD9910.

        :param blind: Do not attempt to verify presence and compatibility.
        """
        cfg = self.cfg_reg
        # Don't pulse MASTER_RESET (m-labs/artiq#940)
        self.cfg_reg = cfg | (0 << CFG_RST) | (1 << CFG_IO_RST)
        if blind:
            self.cfg_write(self.cfg_reg)
        else:
            proto_rev = urukul_sta_proto_rev(self.sta_read())
            if proto_rev != STA_PROTO_REV_MATCH:
                raise ValueError("Urukul proto_rev mismatch")
        delay(100*us)  # reset, slack
        self.cfg_write(cfg)
        if self.sync_div:
            at_mu(now_mu() & ~0xf)  # align to RTIO/2
            self.set_sync_div(self.sync_div)  # 125 MHz/2 = 1 GHz/16
        delay(1*ms)  # DDS wake up

    @kernel
    def io_rst(self):
        """Pulse IO_RST"""
        self.cfg_write(self.cfg_reg | (1 << CFG_IO_RST))
        self.cfg_write(self.cfg_reg & ~(1 << CFG_IO_RST))

    @kernel
    def cfg_sw(self, channel, on):
        """Configure the RF switches through the configuration register.

        These values are logically OR-ed with the LVDS lines on EEM1.

        :param channel: Channel index (0-3)
        :param on: Switch value
        """
        c = self.cfg_reg
        if on:
            c |= 1 << channel
        else:
            c &= ~(1 << channel)
        self.cfg_write(c)

    @kernel
    def cfg_switches(self, state):
        """Configure all four RF switches through the configuration register.

        :param state: RF switch state as a 4 bit integer.
        """
        self.cfg_write((self.cfg_reg & ~0xf) | state)

    @kernel
    def set_att_mu(self, channel, att):
        """Set digital step attenuator in machine units.

        This method will also write the attenuator settings of the three other channels. Use
        :meth:`get_att_mu` to retrieve the hardware state set in previous experiments.

        :param channel: Attenuator channel (0-3).
        :param att: Digital attenuation setting:
            255 minimum attenuation, 0 maximum attenuation (31.5 dB)
        """
        a = self.att_reg & ~(0xff << (channel * 8))
        a |= att << (channel * 8)
        self.set_all_att_mu(a)

    @kernel
    def set_all_att_mu(self, att_reg):
        """Set all four digital step attenuators (in machine units).

        .. seealso:: :meth:`set_att_mu`

        :param att_reg: Attenuator setting string (32 bit)
        """
        self.bus.set_config_mu(SPI_CONFIG | spi.SPI_END, 32,
                               SPIT_ATT_WR, CS_ATT)
        self.bus.write(att_reg)
        self.att_reg = att_reg

    @kernel
    def set_att(self, channel, att):
        """Set digital step attenuator in SI units.

        This method will write the attenuator settings of all four channels.

        .. seealso:: :meth:`set_att_mu`

        :param channel: Attenuator channel (0-3).
        :param att: Attenuation setting in dB. Higher value is more
            attenuation. Minimum attenuation is 0*dB, maximum attenuation is
            31.5*dB.
        """
        self.set_att_mu(channel, 255 - int32(round(att*8)))

    @kernel
    def get_att_mu(self):
        """Return the digital step attenuator settings in machine units.

        The result is stored and will be used in future calls of :meth:`set_att_mu`.

        :return: 32 bit attenuator settings
        """
        self.bus.set_config_mu(SPI_CONFIG | spi.SPI_INPUT, 32,
                               SPIT_ATT_RD, CS_ATT)
        self.bus.write(0)  # shift in zeros, shift out current value
        self.bus.set_config_mu(SPI_CONFIG | spi.SPI_END, 32,
                               SPIT_ATT_WR, CS_ATT)
        delay(10*us)
        self.att_reg = self.bus.read()
        self.bus.write(self.att_reg)  # shift in current value again and latch
        return self.att_reg

    @kernel
    def set_sync_div(self, div):
        """Set the SYNC_IN AD9910 pulse generator frequency
        and align it to the current RTIO timestamp.

        The SYNC_IN signal is derived from the coarse RTIO clock
        and the divider must be a power of two.
        Configure ``sync_sel == 0``.

        :param div: SYNC_IN frequency divider. Must be a power of two.
            Minimum division ratio is 2. Maximum division ratio is 16.
        """
        ftw_max = 1 << 4
        ftw = ftw_max//div
        assert ftw*div == ftw_max
        self.sync.set_mu(ftw)

    @kernel
    def set_profile(self, profile):
        """Set the PROFILE pins.

        The PROFILE pins are common to all four DDS channels.

        :param profile: PROFILE pins in numeric representation (0-7).
        """
        cfg = self.cfg_reg & ~(7 << CFG_PROFILE)
        cfg |= (profile & 7) << CFG_PROFILE
        self.cfg_write(cfg)
