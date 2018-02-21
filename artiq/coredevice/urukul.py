from artiq.language.core import kernel, delay, portable
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
SPIT_ATT_WR = 2
SPIT_ATT_RD = 16
SPIT_DDS_WR = 2
SPIT_DDS_RD = 16

# CFG configuration register bit offsets
CFG_RF_SW = 0
CFG_LED = 4
CFG_PROFILE = 8
CFG_IO_UPDATE = 12
CFG_MASK_NU = 16
CFG_CLK_SEL = 17
CFG_SYNC_SEL = 18
CFG_RST = 19
CFG_IO_RST = 20

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
        clk_sel, sync_sel, rst, io_rst):
    """Build Urukul CPLD configuration register"""
    return ((rf_sw << CFG_RF_SW) |
            (led << CFG_LED) |
            (profile << CFG_PROFILE) |
            (io_update << CFG_IO_UPDATE) |
            (mask_nu << CFG_MASK_NU) |
            (clk_sel << CFG_CLK_SEL) |
            (sync_sel << CFG_SYNC_SEL) |
            (rst << CFG_RST) |
            (io_rst << CFG_IO_RST))


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


class CPLD:
    """Urukul CPLD SPI router and configuration interface.

    :param spi_device: SPI bus device name
    :param io_update_device: IO update RTIO TTLOut channel name
    :param dds_reset_device: DDS reset RTIO TTLOut channel name
    :param refclk: Reference clock (SMA, MMCX or on-board 100 MHz oscillator)
        frequency in Hz
    :param clk_sel: Reference clock selection. 0 corresponds to the internal
        MMCX or ob-board XO clock. 1 corresponds to the front panel SMA.
    :param sync_sel: SYNC clock selection. 0 corresponds to SYNC clock over EEM
        from FPGA. 1 corresponds to SYNC clock from DDS0.
    :param core_device: Core device name
    """
    kernel_invariants = {"refclk", "bus", "core", "io_update"}

    def __init__(self, dmgr, spi_device, io_update_device,
            dds_reset_device=None,
            sync_sel=0, clk_sel=0,
            refclk=125e6, core_device="core"):

        self.core   = dmgr.get(core_device)
        self.refclk = refclk

        self.bus = dmgr.get(spi_device)
        self.io_update = dmgr.get(io_update_device)
        if dds_reset_device is not None:
            self.dds_reset = dmgr.get(dds_reset_device)

        self.cfg_reg = urukul_cfg(rf_sw=0, led=0, profile=0,
            io_update=0, mask_nu=0, clk_sel=clk_sel,
            sync_sel=sync_sel, rst=0, io_rst=0)
        self.att_reg = 0

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
    def init(self):
        """Initialize and detect Urukul.

        Resets the DDS and verifies correct CPLD gateware version.
        """
        cfg = self.cfg_reg
        self.cfg_reg = cfg | (1 << CFG_RST) | (1 << CFG_IO_RST)
        proto_rev = urukul_sta_proto_rev(self.sta_read())
        if proto_rev != STA_PROTO_REV_MATCH:
            raise ValueError("Urukul proto_rev mismatch")
        delay(20*us)  # slack, reset
        self.cfg_write(cfg)
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
    def set_att_mu(self, channel, att):
        """Set digital step attenuator in machine units.

        :param channel: Attenuator channel (0-3).
        :param att: Digital attenuation setting:
            255 minimum attenuation, 0 maximum attenuation (31.5 dB)
        """
        a = self.att_reg & ~(0xff << (channel * 8))
        a |= att << (channel * 8)
        self.bus.set_config_mu(SPI_CONFIG | spi.SPI_END, 32,
                SPIT_ATT_WR, CS_ATT)
        self.bus.write(a)
        self.att_reg = a

    @kernel
    def set_att(self, channel, att):
        """Set digital step attenuator in SI units.

        :param channel: Attenuator channel (0-3).
        :param att: Attenuation setting in dB. Higher value is more
            attenuation.
        """
        self.set_att_mu(channel, 255 - int32(round(att*8)))

    @kernel
    def get_att_mu(self):
        """Return the digital step attenuator settings in machine units.

        :return: 32 bit attenuator settings
        """
        self.bus.set_config_mu(SPI_CONFIG | spi.SPI_END | spi.SPI_INPUT, 32,
                SPIT_ATT_RD, CS_ATT)
        self.bus.write(self.att_reg)
        return self.bus.read()
