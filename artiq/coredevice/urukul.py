from __future__ import annotations

from numpy import int32, int64

from artiq.language.core import *
from artiq.language.units import us, ms

from artiq.coredevice.core import Core
from artiq.coredevice.spi2 import *
from artiq.coredevice.ttl import TTLOut, TTLClockGen


SPI_CONFIG = (
    0 * SPI_OFFLINE
    | 0 * SPI_END
    | 0 * SPI_INPUT
    | 1 * SPI_CS_POLARITY
    | 0 * SPI_CLK_POLARITY
    | 0 * SPI_CLK_PHASE
    | 0 * SPI_LSB_FIRST
    | 0 * SPI_HALF_DUPLEX
)

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
STA_PROTO_REV_8 = 0x08  # See NAC3TODO below for more details
STA_PROTO_REV_9 = 0x09

# chip select (decoded)
CS_CFG = 1
CS_ATT = 2
CS_DDS_MULTI = 3
CS_DDS_CH0 = 4
CS_DDS_CH1 = 5
CS_DDS_CH2 = 6
CS_DDS_CH3 = 7

# Default profile
DEFAULT_PROFILE = 7


@portable
def urukul_sta_rf_sw(sta: int32) -> int32:
    """Return the RF switch status from Urukul status register value."""
    return (sta >> STA_RF_SW) & 0xF


@portable
def urukul_sta_smp_err(sta: int32) -> int32:
    """Return the SMP_ERR status from Urukul status register value."""
    return (sta >> STA_SMP_ERR) & 0xF


@portable
def urukul_sta_pll_lock(sta: int32) -> int32:
    """Return the PLL_LOCK status from Urukul status register value."""
    return (sta >> STA_PLL_LOCK) & 0xF


@portable
def urukul_sta_ifc_mode(sta: int32) -> int32:
    """Return the IFC_MODE status from Urukul status register value."""
    return (sta >> STA_IFC_MODE) & 0xF


@portable
def urukul_sta_proto_rev(sta: int32) -> int32:
    """Return the PROTO_REV value from Urukul status register value."""
    return (sta >> STA_PROTO_REV) & 0x7F


@portable
def urukul_sta_drover(sta: int32) -> int32:
    """Return the DROVER status from Urukul status register value."""
    return (sta >> STA_DROVER) & 0xF


@compile
class _RegIOUpdate:
    cpld: KernelInvariant[CPLD]
    chip_select: KernelInvariant[int32]

    def __init__(self, cpld, chip_select):
        self.cpld = cpld
        self.chip_select = chip_select

    @kernel
    def pulse_mu(self, duration: int64):
        """Pulse the output high for the specified duration
        (in machine units).

        The time cursor is advanced by the specified duration."""
        cfg = self.cpld.cfg_reg
        if self.chip_select == 3:
            self.cpld.cfg_io_update_all(0xF)
        else:
            self.cpld.cfg_io_update(self.chip_select & 0x3, True)
        delay_mu(duration)
        self.cpld.cfg_write(cfg)

    @kernel
    def pulse(self, duration: float):
        """Pulse the output high for the specified duration
        (in seconds).

        The time cursor is advanced by the specified duration."""
        cfg = self.cpld.cfg_reg
        if self.chip_select == 3:
            self.cpld.cfg_io_update_all(0xF)
        else:
            self.cpld.cfg_io_update(self.chip_select & 0x3, True)
        self.cpld.core.delay(duration)
        self.cpld.cfg_write(cfg)


@compile
class _DummySync:
    def __init__(self, cpld):
        self.cpld = cpld

    @kernel
    def set_mu(self, ftw: int32):
        pass


@compile
class CPLDVersion:
    """
    Abstract base class for methods requiring version-specific CPLD implementations.

    Defines interface methods that must be customized for different CPLD versions.
    """
    @kernel
    def cfg_write(self, cpld: CPLD, cfg: int32):
        pass

    @kernel
    def sta_read(self, cpld: CPLD) -> int32:
        return 0

    @kernel
    def init(self, cpld: CPLD, blind: bool):
        pass

    @kernel
    def io_rst(self, cpld: CPLD):
        pass

    @kernel
    def set_profile(self, cpld: CPLD, channel: int32, profile: int32):
        pass

    @kernel
    def _configure_bit(self, cpld: CPLD, bit_offset: int32, channel: int32, on: bool):
        pass

    @kernel
    def _configure_all_bits(self, cpld: CPLD, bit_offset: int32, state: int32):
        pass

    @kernel
    def cfg_mask_nu(self, cpld: CPLD, channel: int32, on: bool):
        pass

    @kernel
    def cfg_mask_nu_all(self, cpld: CPLD, state: int32):
        pass

    @kernel
    def _not_implemented(self):
        raise NotImplementedError(
            "This function is not implemented for this Urukul version."
        )

    @kernel
    def cfg_att_en(self, cpld: CPLD, channel: int32, on: bool):
        self._not_implemented()

    @kernel
    def cfg_att_en_all(self, cpld: CPLD, state: int32):
        self._not_implemented()

    @kernel
    def cfg_osk(self, cpld: CPLD, channel: int32, on: bool):
        self._not_implemented()

    @kernel
    def cfg_osk_all(self, cpld: CPLD, state: int32):
        self._not_implemented()

    @kernel
    def cfg_drctl(self, cpld: CPLD, channel: int32, on: bool):
        self._not_implemented()

    @kernel
    def cfg_drctl_all(self, cpld: CPLD, state: int32):
        self._not_implemented()

    @kernel
    def cfg_drhold(self, cpld: CPLD, channel: int32, on: bool):
        self._not_implemented()

    @kernel
    def cfg_drhold_all(self, cpld: CPLD, state: int32):
        self._not_implemented()

    @kernel
    def cfg_io_update(self, cpld: CPLD, channel: int32, on: bool):
        self._not_implemented()

    @kernel
    def cfg_io_update_all(self, cpld: CPLD, state: int32):
        self._not_implemented()


@compile
class ProtoRev8(CPLDVersion):
    """
    Implementation of the CPLD for Urkul ProtoRev8.
    """

    # ProtoRev8 CFG configuration register bit offsets
    CFG_IO_UPDATE: Kernel[int32] = 12
    CFG_MASK_NU: Kernel[int32] = 13
    CFG_CLK_SEL0: Kernel[int32] = 17
    CFG_CLK_SEL1: Kernel[int32] = 21
    CFG_SYNC_SEL: Kernel[int32] = 18
    CFG_RST: Kernel[int32] = 19
    CFG_IO_RST: Kernel[int32] = 20
    CFG_CLK_DIV: Kernel[int32] = 22

    @portable
    def urukul_cfg(
        self,
        rf_sw: int32,
        led: int32,
        profile: int32,
        io_update: int32,
        mask_nu: int32,
        clk_sel: int32,
        sync_sel: int32,
        rst: int32,
        io_rst: int32,
        clk_div: int32,
    ) -> int64:
        """Build Urukul CPLD configuration register"""
        return int64(
            (rf_sw << CFG_RF_SW)
            | (led << CFG_LED)
            | (profile << CFG_PROFILE)
            | (io_update << ProtoRev8.CFG_IO_UPDATE)
            | (mask_nu << ProtoRev8.CFG_MASK_NU)
            | ((clk_sel & 0x01) << ProtoRev8.CFG_CLK_SEL0)
            | ((clk_sel & 0x02) << (ProtoRev8.CFG_CLK_SEL1 - 1))
            | (sync_sel << ProtoRev8.CFG_SYNC_SEL)
            | (rst << ProtoRev8.CFG_RST)
            | (io_rst << ProtoRev8.CFG_IO_RST)
            | (clk_div << ProtoRev8.CFG_CLK_DIV)
        )

    @kernel
    def cfg_write(self, cpld: CPLD, cfg: int64):
        """Write to the configuration register.
        See :func:`urukul_cfg` for possible flags.
        :param cfg: 24-bit data to be written. Will be stored at
            :attr:`cfg_reg`.
        """
        cpld.bus.set_config_mu(SPI_CONFIG | SPI_END, 24, SPIT_CFG_WR, CS_CFG)
        cpld.bus.write(int32(cfg) << 8)
        cpld.cfg_reg = int64(cfg)

    @kernel
    def sta_read(self, cpld: CPLD) -> int32:
        """Read the status register.
        Use any of the following functions to extract values:
            * :func:`urukul_sta_rf_sw`
            * :func:`urukul_sta_smp_err`
            * :func:`urukul_sta_pll_lock`
            * :func:`urukul_sta_ifc_mode`
            * :func:`urukul_sta_proto_rev`
        :return: The status register value.
        """
        cpld.bus.set_config_mu(
            SPI_CONFIG | SPI_END | SPI_INPUT, 24, SPIT_CFG_RD, CS_CFG
        )
        cpld.bus.write(int32(cpld.cfg_reg << 8))
        return cpld.bus.read()

    @kernel
    def init(self, cpld: CPLD, blind: bool):
        """Initialize Urukul with ProtoRev8.
        Resets the DDS I/O interface.
        Does not pulse the DDS ``MASTER_RESET`` as that confuses the AD9910.
        """
        cfg = cpld.cfg_reg
        # Don't pulse MASTER_RESET (m-labs/artiq#940)
        cpld.cfg_reg = (
            cfg | int64(0 << ProtoRev8.CFG_RST) | int64(1 << ProtoRev8.CFG_IO_RST)
        )
        # Preemptively enable the SPI. Voltages of both common mode and
        # differential are too small initially.
        # This dummy config value is similar to the coming SPI config
        cpld.bus.set_config_mu(SPI_CONFIG, 24, SPIT_CFG_WR, CS_CFG)
        self.core.delay(1.0 * us)
        if blind:
            cpld.cfg_write(cpld.cfg_reg)
        elif urukul_sta_proto_rev(self.sta_read(cpld)) != STA_PROTO_REV_8:
            raise ValueError("Urukul proto_rev mismatch")
        cpld.core.delay(100. * us)  # reset, slack
        cpld.cfg_write(cfg)
        if bool(cpld.sync_div):
            at_mu(now_mu() & ~int64(0xF))  # align to RTIO/2
            cpld.set_sync_div(cpld.sync_div)  # 125 MHz/2 = 1 GHz/16
        cpld.core.delay(1.0 * ms)  # DDS wake up

    @kernel
    def io_rst(self, cpld: CPLD):
        """Pulse IO_RST"""
        cpld.cfg_write(cpld.cfg_reg | int64(1 << ProtoRev8.CFG_IO_RST))
        cpld.cfg_write(cpld.cfg_reg & ~int64(1 << ProtoRev8.CFG_IO_RST))

    @kernel
    def set_profile(self, cpld: CPLD, channel: int32, profile: int32):
        """Set the PROFILE pins.
        The PROFILE pins are common to all four DDS channels.
        :param channel: Channel index (0-3). Unused (here for backwards compatability).
        :param profile: PROFILE pins in numeric representation (0-7).
        """
        cfg = int32(cpld.cfg_reg) & ~(7 << CFG_PROFILE)
        cfg |= (profile & 7) << CFG_PROFILE
        cpld.cfg_write(int64(cfg))

    @kernel
    def _configure_bit(self, cpld: CPLD, bit_offset: int32, channel: int32, on: bool):
        """Configure a single bit in the configuration register.
        :param bit_offset: Base bit offset for the configuration type
        :param channel: Channel index (0-3)
        :param on: Switch value
        """
        c = cpld.cfg_reg
        if on:
            c |= int64(1 << (bit_offset + channel))
        else:
            c &= ~int64(1 << (bit_offset + channel))
        cpld.cfg_write(c)

    @kernel
    def _configure_all_bits(self, cpld: CPLD, bit_offset: int32, state: int32):
        """Configure all four bits at a specific bit offset in the configuration register.
        :param bit_offset: bit offset for the configuration bits
        :param state: State as a 4-bit integer
        """
        cpld.cfg_write(
            (int64(cpld.cfg_reg) & ~int64(0xF << bit_offset))
            | int64(state << bit_offset)
        )

    @kernel
    def cfg_mask_nu(self, cpld: CPLD, channel: int32, on: bool):
        """Configure the MASK_NU bit for the given channel in the configuration register.
        :param channel: Channel index (0-3)
        :param on: Switch value
        """
        cpld._configure_bit(ProtoRev8.CFG_MASK_NU, channel, on)

    @kernel
    def cfg_mask_nu_all(self, cpld: CPLD, state: int32):
        """Configure all four MASK_NU bits in the configuration register.
        :param state: MASK_NU state as a 4-bit integer.
        """
        cpld._configure_all_bits(ProtoRev8.CFG_MASK_NU, state)

    @kernel
    def cfg_io_update(self, cpld: CPLD, channel: int32, on: bool):
        """Configure the IO_UPDATE bit in the configuration register.

        :param channel: Channel index (0-3). Unused (here for backwards compatability).
        :param on: IO_UPDATE state
        """
        cpld._configure_bit(ProtoRev8.CFG_IO_UPDATE, 0, on)

    @kernel
    def cfg_io_update_all(self, cpld: CPLD, state: int32):
        """Configure the IO_UPDATE bit in the configuration register.

        :param state: IO_UPDATE state as a 4-bit integer.
            IO_UPDATE is asserted if any bit(s) is/are asserted, deasserted otherwise.
        """
        self.cfg_io_update(cpld, 0, (state & 0xF) != 0)


@compile
class ProtoRev9:
    """
    Implementation of the CPLD for Urkul ProtoRev9.
    """

    # ProtoRev9 CFG configuration register bit offsets
    CFG_OSK: Kernel[int32] = 20
    CFG_DRCTL: Kernel[int32] = 24
    CFG_DRHOLD: Kernel[int32] = 28
    CFG_IO_UPDATE: Kernel[int32] = 32
    CFG_MASK_NU: Kernel[int32] = 36
    CFG_CLK_SEL0: Kernel[int32] = 40
    CFG_CLK_SEL1: Kernel[int32] = 44
    CFG_SYNC_SEL: Kernel[int32] = 41
    CFG_RST: Kernel[int32] = 42
    CFG_IO_RST: Kernel[int32] = 43
    CFG_CLK_DIV: Kernel[int32] = 45
    CFG_ATT_EN: Kernel[int32] = 47

    @portable
    def urukul_cfg(
        self,
        rf_sw: int32,
        led: int32,
        profile: int32,
        osk: int32,
        drctl: int32,
        drhold: int32,
        io_update: int32,
        mask_nu: int32,
        clk_sel: int32,
        sync_sel: int32,
        rst: int32,
        io_rst: int32,
        clk_div: int32,
        att_en: int32,
    ) -> int64:
        """Build Urukul CPLD configuration register"""
        return int64(
            (rf_sw << CFG_RF_SW)
            | (led << CFG_LED)
            | (profile << CFG_PROFILE)
            | (osk << ProtoRev9.CFG_OSK)
            | (drctl << ProtoRev9.CFG_DRCTL)
            | (drhold << ProtoRev9.CFG_DRHOLD)
            | (io_update << ProtoRev9.CFG_IO_UPDATE)
            | (mask_nu << ProtoRev9.CFG_MASK_NU)
            | ((clk_sel & 0x01) << ProtoRev9.CFG_CLK_SEL0)
            | ((clk_sel & 0x02) << (ProtoRev9.CFG_CLK_SEL1 - 1))
            | (sync_sel << ProtoRev9.CFG_SYNC_SEL)
            | (rst << ProtoRev9.CFG_RST)
            | (io_rst << ProtoRev9.CFG_IO_RST)
            | (clk_div << ProtoRev9.CFG_CLK_DIV)
            | (att_en << ProtoRev9.CFG_ATT_EN)
        )

    @kernel
    def cfg_write(self, cpld: CPLD, cfg: int64):
        """Write to the configuration register.
        See :func:`urukul_cfg` for possible flags.
        :param cfg: 52-bit data to be written. Will be stored at
            :attr:`cfg_reg`.
        """
        cpld.bus.set_config_mu(SPI_CONFIG, 24, SPIT_CFG_WR, CS_CFG)
        cpld.bus.write(((int32(cfg) >> 28) & 0xFFFFFF) << 8)
        cpld.bus.set_config_mu(SPI_CONFIG | SPI_END, 28, SPIT_CFG_WR, CS_CFG)
        cpld.bus.write((int32(cfg) & 0xFFFFFFF) << 4)
        cpld.cfg_reg = cfg

    @kernel
    def sta_read(self, cpld: CPLD) -> int32:
        """Read the status register.
        Use any of the following functions to extract values:
            * :func:`urukul_sta_rf_sw`
            * :func:`urukul_sta_smp_err`
            * :func:`urukul_sta_pll_lock`
            * :func:`urukul_sta_ifc_mode`
            * :func:`urukul_sta_proto_rev`
            * :func:`urukul_sta_drover`
        :return: The status register value.
        """
        cpld.bus.set_config_mu(SPI_CONFIG, 24, SPIT_CFG_WR, CS_CFG)
        cpld.bus.write((int32((cpld.cfg_reg >> 28) & int64(0xFFFFFF)) << 8))
        cpld.bus.set_config_mu(
            SPI_CONFIG | SPI_END | SPI_INPUT, 28, SPIT_CFG_RD, CS_CFG
        )
        cpld.bus.write(int32((cpld.cfg_reg & int64(0xFFFFFFF)) << 4))
        return cpld.bus.read()

    @kernel
    def init(self, cpld: CPLD, blind: bool):
        """Initialize Urukul with ProtoRev9.
        Resets the DDS I/O interface.
        Does not pulse the DDS ``MASTER_RESET`` as that confuses the AD9910.
        """
        cfg = cpld.cfg_reg
        # Don't pulse MASTER_RESET (m-labs/artiq#940)
        cpld.cfg_reg = (
            cfg | (int64(0) << ProtoRev9.CFG_RST) | (int64(1) << ProtoRev9.CFG_IO_RST)
        )
        # Preemptively enable the SPI. Voltages of both common mode and
        # differential are too small initially.
        # This dummy config value is the coming SPI config
        cpld.bus.set_config_mu(SPI_CONFIG, 24, SPIT_CFG_WR, CS_CFG)
        delay(1.0 * us)
        if blind:
            cpld.cfg_write(cpld.cfg_reg)
        elif urukul_sta_proto_rev(self.sta_read(cpld))!= STA_PROTO_REV_9:
            raise ValueError("Urukul proto_rev mismatch")
        cpld.core.delay(100. * us)  # reset, slack
        cpld.cfg_write(cfg)
        if bool(cpld.sync_div):
            at_mu(now_mu() & ~int64(0xF))  # align to RTIO/2
            cpld.set_sync_div(cpld.sync_div)  # 125 MHz/2 = 1 GHz/16
        cpld.core.delay(1.0 * ms)  # DDS wake up

    @kernel
    def io_rst(self, cpld: CPLD):
        """Pulse IO_RST"""
        cpld.cfg_write(cpld.cfg_reg | (int64(1) << ProtoRev9.CFG_IO_RST))
        cpld.cfg_write(cpld.cfg_reg & ~(int64(1) << ProtoRev9.CFG_IO_RST))

    @kernel
    def set_profile(self, cpld: CPLD, channel: int32, profile: int32):
        """Set the CFG.PROFILE[0:2] pins for the given channel.
        :param channel: Channel (0-3).
        :param profile: PROFILE pins in numeric representation (0-7).
        """
        cfg = cpld.cfg_reg & ~int64(7 << (CFG_PROFILE + channel * 3))
        cfg |= int64((profile & 7) << (CFG_PROFILE + channel * 3))
        cpld.cfg_write(cfg)

    @kernel
    def _configure_bit(self, cpld: CPLD, bit_offset: int32, channel: int32, on: bool):
        """Configure a single bit in the configuration register.
        :param bit_offset: Base bit offset for the configuration type
        :param channel: Channel index (0-3)
        :param on: Switch value
        """
        c = cpld.cfg_reg
        if on:
            c = int64(c) | int64(1) << (bit_offset + channel)
        else:
            c = int64(c) & ~(int64(1) << (bit_offset + channel))
        cpld.cfg_write(c)

    @kernel
    def _configure_all_bits(self, cpld: CPLD, bit_offset: int32, state: int32):
        """Configure all four bits at a specific bit offset in the configuration register.
        :param bit_offset: bit offset for the configuration bits
        :param state: State as a 4-bit integer
        """
        cpld.cfg_write(
            (int64(cpld.cfg_reg) & ~(int64(0xF) << bit_offset))
            | (int64(state) << bit_offset)
        )

    @kernel
    def cfg_mask_nu(self, cpld: CPLD, channel: int32, on: bool):
        """Configure the MASK_NU bit for the given channel in the configuration register.
        :param channel: Channel index (0-3)
        :param on: Switch value
        """
        cpld._configure_bit(ProtoRev9.CFG_MASK_NU, channel, on)

    @kernel
    def cfg_mask_nu_all(self, cpld: CPLD, state: int32):
        """Configure all four MASK_NU bits in the configuration register.
        :param state: MASK_NU state as a 4-bit integer.
        """
        cpld._configure_all_bits(ProtoRev9.CFG_MASK_NU, state)

    @kernel
    def cfg_att_en(self, cpld: CPLD, channel: int32, on: bool):
        """Configure the ATT_EN bit for the given channel in the configuration register.
        :param channel: Channel index (0-3)
        :param on: Switch value
        """
        cpld._configure_bit(ProtoRev9.CFG_ATT_EN, channel, on)

    @kernel
    def cfg_att_en_all(self, cpld: CPLD, state: int32):
        """Configure all four ATT_EN bits in the configuration register.

        :param state: ATT_EN state as a 4-bit integer.
        """
        cpld._configure_all_bits(ProtoRev9.CFG_ATT_EN, state)

    @kernel
    def cfg_osk(self, cpld: CPLD, channel: int32, on: bool):
        """Configure the OSK bit for the given channel in the configuration register.
        :param channel: Channel index (0-3)
        :param on: Switch value
        """
        cpld._configure_bit(ProtoRev9.CFG_OSK, channel, on)

    @kernel
    def cfg_osk_all(self, cpld: CPLD, state: int32):
        """Configure all four OSK bits in the configuration register.
        :param state: OSK state as a 4-bit integer.
        """
        cpld._configure_all_bits(ProtoRev9.CFG_OSK, state)

    @kernel
    def cfg_drctl(self, cpld: CPLD, channel: int32, on: bool):
        """Configure the DRCTL bit for the given channel in the configuration register.
        :param channel: Channel index (0-3)
        :param on: Switch value
        """
        cpld._configure_bit(ProtoRev9.CFG_DRCTL, channel, on)

    @kernel
    def cfg_drctl_all(self, cpld: CPLD, state: int32):
        """Configure all four DRCTL bits in the configuration register.
        :param state: DRCTL state as a 4-bit integer.
        """
        cpld._configure_all_bits(ProtoRev9.CFG_DRCTL, state)

    @kernel
    def cfg_drhold(self, cpld: CPLD, channel: int32, on: bool):
        """Configure the DRHOLD bit for the given channel in the configuration register.
        :param channel: Channel index (0-3)
        :param on: Switch value
        """
        cpld._configure_bit(ProtoRev9.CFG_DRHOLD, channel, on)

    @kernel
    def cfg_drhold_all(self, cpld: CPLD, state: int32):
        """Configure all four DRHOLD bits in the configuration register.
        :param state: DRHOLD state as a 4-bit integer.
        """
        cpld._configure_all_bits(ProtoRev9.CFG_DRHOLD, state)

    @kernel
    def cfg_io_update(self, cpld, channel: TInt32, on: TBool):
        """Configure the IO_UPDATE bit for the given channel in the configuration register.

        :param channel: Channel index (0-3)
        :param on: IO_UPDATE state
        """
        cpld._configure_bit(ProtoRev9.CFG_IO_UPDATE, channel, on)

    @kernel
    def cfg_io_update_all(self, cpld, state: TInt32):
        """Configure all four IO_UPDATE bits in the configuration register.

        :param state: IO_UPDATE state as a 4-bit integer.
        """
        cpld._configure_all_bits(ProtoRev9.CFG_IO_UPDATE, state)


@compile
class CPLD:
    """Urukul CPLD SPI router and configuration interface.

    :param spi_device: SPI bus device name
    :param io_update_device: IO update RTIO TTLOut channel name
    :param dds_reset_device: DDS reset RTIO TTLOut channel name
    :param sync_device: AD9910 ``SYNC_IN`` RTIO TTLClockGen channel name
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
    :param sync_sel: ``SYNC`` (multi-chip synchronisation) signal source selection.
        0 corresponds to ``SYNC_IN`` being supplied by the FPGA via the EEM
        connector. 1 corresponds to ``SYNC_OUT`` from DDS0 being distributed to the
        other chips.
    :param rf_sw: Initial CPLD RF switch register setting (default: 0x0).
        Knowledge of this state is not transferred between experiments.
    :param att: Initial attenuator setting shift register (default:
        0x00000000). See also :meth:`get_att_mu` which retrieves the hardware
        state without side effects. Knowledge of this state is not transferred
        between experiments.
    :param sync_div: ``SYNC_IN`` generator divider. The ratio between the coarse
        RTIO frequency and the ``SYNC_IN`` generator frequency (default: 2 if
        `sync_device` was specified).
    :param core_device: Core device name

    If the clocking is incorrect (for example, setting ``clk_sel`` to the
    front panel SMA with no clock connected), then the ``init()`` method of
    the DDS channels can fail with the error message ``PLL lock timeout``.
    """

    core: KernelInvariant[Core]
    refclk: KernelInvariant[float]
    bus: KernelInvariant[SPIMaster]
    io_update: KernelInvariant[TTLOut]
    clk_div: KernelInvariant[int32]
    dds_reset: KernelInvariant[Option[TTLOut]]
    sync: KernelInvariant[Option[TTLClockGen]]
    cfg_reg: Kernel[int64]
    att_reg: Kernel[int32]
    sync_div: Kernel[int32]
    proto_rev: Kernel[int32]
    # NAC3TODO
    #
    # Currently, only proto_rev=0x09 is supported. This is due to the following limitations:
    #
    # - Inheritance between base and derived classes is not fully supported.
    # - Generics (TypeVar/Generic) can be used to work around this.
    # - However, application of type vars to a generic class is not currently supported (e.g.):
    #
    #           class A(Generic[T]):
    #               def __init__(self):
    #                   pass
    #               def fun(self, a: A[T]) -> A[T]:
    #                   pass
    #
    # TODO: Add other proto_revs once supported.
    version: KernelInvariant[ProtoRev9]

    def __init__(
        self,
        dmgr,
        spi_device,
        io_update_device=None,
        dds_reset_device=None,
        sync_device=None,
        sync_sel=0,
        clk_sel=0,
        clk_div=0,
        rf_sw=0,
        refclk=125e6,
        att=0x00000000,
        sync_div=None,
        proto_rev=0x09,
        core_device="core",
    ):
        self.core = dmgr.get(core_device)
        self.refclk = refclk
        assert 0 <= clk_div <= 3
        self.clk_div = clk_div

        self.bus = dmgr.get(spi_device)
        if io_update_device is not None:
            self.io_update = dmgr.get(io_update_device)
        else:
            self.io_update = _RegIOUpdate(self.core, self)
            # NAC3TODO
            raise NotImplementedError
        if dds_reset_device is not None:
            self.dds_reset = Some(dmgr.get(dds_reset_device))
        else:
            self.dds_reset = none
        if sync_device is not None:
            self.sync = Some(dmgr.get(sync_device))
            if sync_div is None:
                sync_div = 2
        else:
            self.sync = none
            assert sync_div is None
            sync_div = 0

        self.proto_rev = proto_rev
        if proto_rev == STA_PROTO_REV_8 or proto_rev != STA_PROTO_REV_9:
            raise ValueError(f"NAC3: Urukul unsupported proto_rev: {proto_rev}")
        self.version = ProtoRev9()

        # NAC3TODO
        # if self.proto_rev == STA_PROTO_REV_8:
        #     self.cfg_reg = int64(
        #         self.version.urukul_cfg(
        #             rf_sw=rf_sw,
        #             led=0,
        #             profile=DEFAULT_PROFILE,
        #             io_update=0,
        #             mask_nu=0,
        #             clk_sel=clk_sel,
        #             sync_sel=sync_sel,
        #             rst=0,
        #             io_rst=0,
        #             clk_div=clk_div,
        #         )
        #     )
        # else:
        self.cfg_reg = int64(
            self.version.urukul_cfg(
                rf_sw=rf_sw,
                led=0,
                profile=(DEFAULT_PROFILE << 9)
                | (DEFAULT_PROFILE << 6)
                | (DEFAULT_PROFILE << 3)
                | DEFAULT_PROFILE,
                osk=0,
                drctl=0,
                drhold=0,
                io_update=0,
                mask_nu=0,
                clk_sel=clk_sel,
                sync_sel=sync_sel,
                rst=0,
                io_rst=0,
                clk_div=clk_div,
                att_en=0b1111,
            ))
        self.att_reg = int32(int64(att))
        self.sync_div = sync_div

    @kernel
    def cfg_write(self, cfg: int64):
        self.version.cfg_write(self, cfg)

    @kernel
    def sta_read(self) -> int32:
        return self.version.sta_read(self)

    @kernel
    def init(self, blind: bool = False):
        self.version.init(self, blind)

    @kernel
    def io_rst(self):
        self.version.io_rst(self)

    @kernel
    def set_profile(self, channel: int32, profile: int32):
        self.version.set_profile(self, channel, profile)

    @kernel
    def _configure_bit(self, bit_offset: int32, channel: int32, on: bool):
        self.version._configure_bit(self, bit_offset, channel, on)

    @kernel
    def _configure_all_bits(self, bit_offset: int32, state: int32):
        self.version._configure_all_bits(self, bit_offset, state)

    @kernel
    def cfg_mask_nu(self, channel: int32, on: bool):
        self.version.cfg_mask_nu(self, channel, on)

    @kernel
    def cfg_mask_nu_all(self, state: int32):
        self.version.cfg_mask_nu_all(self, state)

    @kernel
    def cfg_att_en(self, channel: int32, on: bool):
        self.version.cfg_att_en(self, channel, on)

    @kernel
    def cfg_att_en_all(self, state: int32):
        self.version.cfg_att_en_all(self, state)

    @kernel
    def cfg_osk(self, channel: int32, on: bool):
        self.version.cfg_osk(self, channel, on)

    @kernel
    def cfg_osk_all(self, state: int32):
        self.version.cfg_osk_all(self, state)

    @kernel
    def cfg_drctl(self, channel: int32, on: bool):
        self.version.cfg_drctl(self, channel, on)

    @kernel
    def cfg_drctl_all(self, state: int32):
        self.version.cfg_drctl_all(self, state)

    @kernel
    def cfg_drhold(self, channel: int32, on: bool):
        self.version.cfg_drhold(self, channel, on)

    @kernel
    def cfg_drhold_all(self, state: int32):
        self.version.cfg_drhold_all(self, state)
    
    @kernel
    def cfg_io_update(self, channel: TInt32, on: TBool):
        self.version.cfg_io_update(self, channel, on)

    @kernel
    def cfg_io_update_all(self, state: TInt32):
        self.version.cfg_io_update_all(self, state)

    @kernel
    def cfg_sw(self, channel: int32, on: bool):
        """Configure the RF switches through the configuration register.

        These values are logically OR-ed with the LVDS lines on EEM1.

        :param channel: Channel index (0-3)
        :param on: Switch value
        """
        c = self.cfg_reg
        if on:
            c |= int64(1 << channel)
        else:
            c &= ~int64(1 << channel)
        self.cfg_write(c)

    @kernel
    def cfg_switches(self, state: int32):
        """Configure all four RF switches through the configuration register.

        :param state: RF switch state as a 4-bit integer.
        """
        self.cfg_write((self.cfg_reg & ~int64(0xF)) | int64(state))

    @portable
    def mu_to_att(self, att_mu: int32) -> float:
        """Convert a digital attenuation setting to dB.

        :param att_mu: Digital attenuation setting.
        :return: Attenuation setting in dB.
        """
        return (255 - (att_mu & 0xFF)) / 8

    @portable
    def att_to_mu(self, att: float) -> int32:
        """Convert an attenuation setting in dB to machine units.

        :param att: Attenuation setting in dB.
        :return: Digital attenuation setting.
        """
        code = 255 - round(att * 8.0)
        if code < 0 or code > 255:
            raise ValueError("Invalid urukul.CPLD attenuation!")
        return code

    @kernel
    def set_att_mu(self, channel: int32, att: int32):
        """Set digital step attenuator in machine units.

        This method will also write the attenuator settings of the three
        other channels. Use :meth:`get_att_mu` to retrieve the hardware
        state set in previous experiments.

        :param channel: Attenuator channel (0-3).
        :param att: 8-bit digital attenuation setting:
            255 minimum attenuation, 0 maximum attenuation (31.5 dB)
        """
        a = self.att_reg & ~(0xFF << (channel * 8))
        a |= att << (channel * 8)
        self.set_all_att_mu(a)

    @kernel
    def set_all_att_mu(self, att_reg: int32):
        """Set all four digital step attenuators (in machine units).
        See also :meth:`set_att_mu`.

        :param att_reg: Attenuator setting string (32-bit)
        """
        self.bus.set_config_mu(SPI_CONFIG | SPI_END, 32, SPIT_ATT_WR, CS_ATT)
        self.bus.write(att_reg)
        self.att_reg = att_reg

    @kernel
    def set_att(self, channel: int32, att: float):
        """Set digital step attenuator in SI units.

        This method will write the attenuator settings of all four channels.
        See also :meth:`set_att_mu`.

        :param channel: Attenuator channel (0-3).
        :param att: Attenuation setting in dB. Higher value is more
            attenuation. Minimum attenuation is 0*dB, maximum attenuation is
            31.5*dB.
        """
        self.set_att_mu(channel, self.att_to_mu(att))

    @kernel
    def get_att_mu(self) -> int32:
        """Return the digital step attenuator settings in machine units.

        The result is stored and will be used in future calls of
        :meth:`set_att_mu` and :meth:`set_att`.

        See also :meth:`get_channel_att_mu`.

        :return: 32-bit attenuator settings
        """
        self.bus.set_config_mu(SPI_CONFIG | SPI_INPUT, 32, SPIT_ATT_RD, CS_ATT)
        self.bus.write(0)  # shift in zeros, shift out current value
        self.bus.set_config_mu(SPI_CONFIG | SPI_END, 32, SPIT_ATT_WR, CS_ATT)
        self.core.delay(10.0 * us)
        self.att_reg = self.bus.read()
        self.bus.write(self.att_reg)  # shift in current value again and latch
        return self.att_reg

    @kernel
    def get_channel_att_mu(self, channel: int32) -> int32:
        """Get digital step attenuator value for a channel in machine units.

        The result is stored and will be used in future calls of
        :meth:`set_att_mu` and :meth:`set_att`.

        See also :meth:`get_att_mu`.

        :param channel: Attenuator channel (0-3).
        :return: 8-bit digital attenuation setting:
            255 minimum attenuation, 0 maximum attenuation (31.5 dB)
        """
        return int32((self.get_att_mu() >> (channel * 8)) & 0xFF)

    @kernel
    def get_channel_att(self, channel: int32) -> float:
        """Get digital step attenuator value for a channel in SI units.

        See also :meth:`get_channel_att_mu`.

        :param channel: Attenuator channel (0-3).
        :return: Attenuation setting in dB. Higher value is more
            attenuation. Minimum attenuation is 0*dB, maximum attenuation is
            31.5*dB.
        """
        return self.mu_to_att(self.get_channel_att_mu(channel))

    @kernel
    def set_sync_div(self, div: int32):
        """Set the ``SYNC_IN`` AD9910 pulse generator frequency
        and align it to the current RTIO timestamp.

        The ``SYNC_IN`` signal is derived from the coarse RTIO clock
        and the divider must be a power of two.
        Configure ``sync_sel == 0``.

        :param div: ``SYNC_IN`` frequency divider. Must be a power of two.
            Minimum division ratio is 2. Maximum division ratio is 16.
        """
        ftw_max = 1 << 4
        ftw = ftw_max // div
        assert ftw * div == ftw_max
        if self.sync.is_some():
            self.sync.unwrap().set_mu(ftw)


@compile
class _RegIOUpdate:
    core: KernelInvariant[Core]
    cpld: KernelInvariant[CPLD]
    chip_select: KernelInvariant[int32]

    def __init__(self, core, cpld, chip_select):
        self.core = core
        self.cpld = cpld
        self.chip_select = chip_select

    @kernel
    def pulse_mu(self, t: int64):
        """Pulse the output high for the specified duration
        (in machine units).
        The time cursor is advanced by the specified duration."""
        cfg = self.cpld.cfg_reg
        # NAC3TODO
        # if self.cpld.proto_rev == STA_PROTO_REV_8:
        #     self.cpld.cfg_write(cfg | int64(1 << ProtoRev8.CFG_IO_UPDATE))
        # else:
        self.cpld.cfg_write(
            int64(cfg)
            | (int64(1) << (ProtoRev9.CFG_IO_UPDATE + (self.chip_select - 4)))
        )
        delay_mu(t)
        self.cpld.cfg_write(cfg)

    @kernel
    def pulse(self, t: float):
        """Pulse the output high for the specified duration
        (in seconds).
        The time cursor is advanced by the specified duration."""
        cfg = self.cpld.cfg_reg
        # NAC3TODO
        # if self.cpld.proto_rev == STA_PROTO_REV_8:
        #     self.cpld.cfg_write(cfg | int64(1 << ProtoRev8.CFG_IO_UPDATE))
        # else:
        self.cpld.cfg_write(
            int64(cfg)
            | (int64(1) << (ProtoRev9.CFG_IO_UPDATE + (self.chip_select - 4)))
        )
        self.cpld.core.delay(t)
        self.cpld.cfg_write(cfg)
