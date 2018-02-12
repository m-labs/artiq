from artiq.language.core import kernel, delay_mu, delay, now_mu, at_mu
from artiq.language.units import us, ms

from numpy import int32, int64

from artiq.coredevice import spi


_SPI_CONFIG = (0*spi.SPI_OFFLINE | 1*spi.SPI_CS_POLARITY |
        0*spi.SPI_CLK_POLARITY | 0*spi.SPI_CLK_PHASE |
        0*spi.SPI_LSB_FIRST | 0*spi.SPI_HALF_DUPLEX)

# SPI clock write and read dividers
_SPIT_CFG_WR = 2
_SPIT_CFG_RD = 16
_SPIT_ATT_WR = 2
_SPIT_ATT_RD = 16
_SPIT_DDS_WR = 3
_SPIT_DDS_RD = 16

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


@kernel
def urukul_cfg(rf_sw, led, profile, io_update, mask_nu,
        clk_sel, sync_sel, rst, io_rst):
    return ((rf_sw << CFG_RF_SW) | (led << CFG_LED) |
            (profile << CFG_PROFILE) |
            (io_update << CFG_IO_UPDATE) | (mask_nu << CFG_MASK_NU) |
            (clk_sel << CFG_CLK_SEL) | (sync_sel << CFG_SYNC_SEL) |
            (rst << CFG_RST) | (io_rst << CFG_IO_RST))


# STA status register bit offsets
STA_RF_SW = 0
STA_SMP_ERR = 4
STA_PLL_LOCK = 8
STA_IFC_MODE = 12
STA_PROTO_REV = 16


@kernel
def urukul_sta_rf_sw(sta):
    return (sta >> STA_RF_SW) & 0xf


@kernel
def urukul_sta_smp_err(sta):
    return (sta >> STA_SMP_ERR) & 0xf


@kernel
def urukul_sta_pll_lock(sta):
    return (sta >> STA_PLL_LOCK) & 0xf


@kernel
def urukul_sta_ifc_mode(sta):
    return (sta >> STA_IFC_MODE) & 0xf


@kernel
def urukul_sta_proto_rev(sta):
    return (sta >> STA_PROTO_REV) & 0xff


# supported hardware and CPLD code version
STA_PROTO_REV_MATCH = 0x07

# chip select (decoded)
CS_CFG = 1
CS_ATT = 2
CS_DDS_MULTI = 3
CS_DDS_CH0 = 4
CS_DDS_CH1 = 5
CS_DDS_CH2 = 6
CS_DDS_CH3 = 7


class CPLD:
    def __init__(self, dmgr, spi_device, io_update_device,
            dds_reset_device=None,
            refclk=100e6, core_device="core"):

        self.core   = dmgr.get(core_device)
        self.refclk = refclk

        self.bus = dmgr.get(spi_device)
        self.io_update = dmgr.get(io_update_device)
        if dds_reset_device is not None:
            self.dds_reset = dmgr.get(dds_reset_device)

        self.cfg_reg = int32(0)
        self.att_reg = int32(0)

    @kernel
    def cfg_write(self, cfg_reg):
        self.bus.set_config_mu(_SPI_CONFIG, _SPIT_CFG_WR, _SPIT_CFG_RD)
        self.bus.set_xfer(CS_CFG, 24, 0)
        self.bus.write(cfg_reg << 8)
        self.bus.set_config_mu(_SPI_CONFIG, _SPIT_DDS_WR, _SPIT_DDS_RD)
        self.cfg_reg = cfg_reg

    @kernel
    def sta_read(self):
        self.cfg_write(self.cfg_reg)  # to latch STA
        self.bus.set_config_mu(_SPI_CONFIG, _SPIT_CFG_WR, _SPIT_CFG_RD)
        self.bus.set_xfer(CS_CFG, 0, 24)
        self.bus.write(self.cfg_reg << 8)
        self.bus.set_config_mu(_SPI_CONFIG, _SPIT_DDS_WR, _SPIT_DDS_RD)
        return self.bus.read_sync()

    @kernel
    def init(self, clk_sel=0, sync_sel=0):
        cfg = urukul_cfg(rf_sw=0, led=0, profile=0,
            io_update=0, mask_nu=0, clk_sel=clk_sel,
            sync_sel=sync_sel, rst=0, io_rst=0)
        self.cfg_write(cfg | (1 << CFG_RST) | (1 << CFG_IO_RST))
        delay(1*ms)
        self.cfg_write(cfg)
        delay(10*ms)  # DDS wake up
        proto_rev = urukul_sta_proto_rev(self.sta_read())
        if proto_rev != STA_PROTO_REV_MATCH:
            raise ValueError("Urukul proto_rev mismatch")
        delay(100*us)

    @kernel
    def io_rst(self):
        delay(1*us)
        self.cfg_write(self.cfg_reg | (1 << CFG_IO_RST))
        delay(1*us)
        self.cfg_write(self.cfg_reg & ~(1 << CFG_IO_RST))
        delay(1*us)

    @kernel
    def cfg_sw(self, sw, on):
        c = self.cfg_reg
        if on:
            c |= 1 << sw
        else:
            c &= ~(1 << sw)
        self.cfg_write(c)

    @kernel
    def set_att_mu(self, channel, att):
        """
        Parameters:
            att (int): 0-255, 255 minimum attenuation,
                0 maximum attenuation (31.5 dB)
        """
        a = self.att_reg & ~(0xff << (channel * 8))
        a |= att << (channel * 8)
        self.att_reg = a
        self.bus.set_config_mu(_SPI_CONFIG, _SPIT_ATT_WR, _SPIT_ATT_RD)
        self.bus.set_xfer(CS_ATT, 32, 0)
        self.bus.write(a)

    @kernel
    def set_att(self, channel, att):
        self.set_att_mu(channel, 255 - int32(round(att*8)))
