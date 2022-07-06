from migen import *

from artiq.gateware import ad9_dds
from artiq.gateware.rtio.phy.wishbone import RT2WB

from artiq.coredevice.spi2 import SPI_CONFIG_ADDR, SPI_DATA_ADDR, SPI_END
from artiq.coredevice.urukul import CS_DDS_CH0, CS_DDS_MULTI, CFG_IO_UPDATE, CS_CFG

from artiq.coredevice.ad9912_reg import AD9912_POW1
from artiq.coredevice.ad9910 import _AD9910_REG_PROFILE0, _AD9910_REG_PROFILE7, _AD9910_REG_FTW

class AD9914(Module):
    def __init__(self, pads, nchannels, onehot=False, **kwargs):
        self.submodules._ll = ClockDomainsRenamer("rio_phy")(
            ad9_dds.AD9_DDS(pads, **kwargs))
        self.submodules._rt2wb = RT2WB(len(pads.a)+1, self._ll.bus, write_only=True)
        self.rtlink = self._rt2wb.rtlink
        self.probes = [Signal(32) for i in range(nchannels)]

        # # #

        # buffer the current address/data on the rtlink output
        current_address = Signal.like(self.rtlink.o.address)
        current_data = Signal.like(self.rtlink.o.data)
        self.sync.rio += If(self.rtlink.o.stb,
                            current_address.eq(self.rtlink.o.address),
                            current_data.eq(self.rtlink.o.data))

        # keep track of the currently selected channel(s)
        current_sel = Signal(len(current_data)-1)
        self.sync.rio += If(current_address == 2**len(pads.a) + 1,
                            current_sel.eq(current_data[1:]))  # strip reset

        def selected(c):
            if onehot:
                return current_sel[c]
            else:
                return current_sel == c

        # keep track of frequency tuning words, before they are FUDed
        ftws = [Signal(32) for i in range(nchannels)]
        for c, ftw in enumerate(ftws):
            if len(pads.d) == 8:
                self.sync.rio_phy += \
                    If(selected(c), [
                        If(current_address == 0x11+i,
                           ftw[i*8:(i+1)*8].eq(current_data))
                        for i in range(4)])
            elif len(pads.d) == 16:
                self.sync.rio_phy += \
                    If(selected(c), [
                        If(current_address == 0x11+2*i,
                           ftw[i*16:(i+1)*16].eq(current_data))
                        for i in range(2)])
            else:
                raise NotImplementedError

        # FTW to probe on FUD
        self.sync.rio_phy += If(current_address == 2**len(pads.a), [
            If(selected(c), probe.eq(ftw))
            for c, (probe, ftw) in enumerate(zip(self.probes, ftws))])


class UrukulMonitor(Module):
    def __init__(self, spi_phy, io_update_phy, dds, nchannels=4):
        self.spi_phy = spi_phy
        self.io_update_phy = io_update_phy

        self.probes = [Signal(32) for i in range(nchannels)]

        self.cs = Signal(8)
        self.current_data = Signal.like(self.spi_phy.rtlink.o.data)
        current_address = Signal.like(self.spi_phy.rtlink.o.address)
        data_length = Signal(8)
        flags = Signal(8)

        self.sync.rio += If(self.spi_phy.rtlink.o.stb, [
            current_address.eq(self.spi_phy.rtlink.o.address),
            self.current_data.eq(self.spi_phy.rtlink.o.data),
            If(self.spi_phy.rtlink.o.address == SPI_CONFIG_ADDR, [
                self.cs.eq(self.spi_phy.rtlink.o.data[24:]),
                data_length.eq(self.spi_phy.rtlink.o.data[8:16] + 1),
                flags.eq(self.spi_phy.rtlink.o.data[0:8])
            ])
        ])

        for i in range(nchannels):
            ch_sel = Signal()
            self.comb += ch_sel.eq(
                ((self.cs == CS_DDS_MULTI) | (self.cs == i + CS_DDS_CH0)) 
                & (current_address == SPI_DATA_ADDR)
            )

            if dds == "ad9912":
                mon_cls = _AD9912Monitor
            elif dds == "ad9910":
                mon_cls = _AD9910Monitor
            else:
                raise NotImplementedError

            monitor = mon_cls(self.current_data, data_length, flags, ch_sel)
            self.submodules += monitor

            self.sync.rio_phy += [
                If(ch_sel & self.is_io_update(), self.probes[i].eq(monitor.ftw))
            ]

    def is_io_update(self):
        # shifted 8 bits left for 32-bit bus
        reg_io_upd = (self.cs == CS_CFG) & self.current_data[8 + CFG_IO_UPDATE]
        phy_io_upd = False
        if self.io_update_phy:
            phy_io_upd = self.io_update_phy.rtlink.o.stb & self.io_update_phy.rtlink.o.data
        return phy_io_upd | reg_io_upd


class _AD9912Monitor(Module):
    def __init__(self, current_data, data_length, flags, ch_sel):
        self.ftw = Signal(32, reset_less=True)

        fsm = ClockDomainsRenamer("rio_phy")(FSM(reset_state="IDLE"))
        self.submodules += fsm

        reg_addr = current_data[16:29]
        reg_write = ~current_data[31]

        fsm.act("IDLE", 
            If(ch_sel & reg_write,
                If((data_length == 16) & (reg_addr == AD9912_POW1),
                    NextState("READ")
                )
            )
        )

        fsm.act("READ",
            If(ch_sel,
                If(flags & SPI_END,
                    # lower 16 bits (16-32 from 48-bit transfer)
                    NextValue(self.ftw[:16], current_data[16:]),
                    NextState("IDLE")
                ).Else(
                    NextValue(self.ftw[16:], current_data[:16])
                )
            )
        )


class _AD9910Monitor(Module):
    def __init__(self, current_data, data_length, flags, ch_sel):
        self.ftw = Signal(32, reset_less=True)

        fsm = ClockDomainsRenamer("rio_phy")(FSM(reset_state="IDLE"))
        self.submodules += fsm

        reg_addr = current_data[24:29]
        reg_write = ~current_data[31]

        fsm.act("IDLE", 
            If(ch_sel & reg_write,
                If((data_length == 8) & (_AD9910_REG_PROFILE7 >= reg_addr) & (reg_addr >= _AD9910_REG_PROFILE0),
                    NextState("READ")
                ).Elif(reg_addr == _AD9910_REG_FTW,
                    If((data_length == 24) & (flags & SPI_END),
                        NextValue(self.ftw[:16], current_data[8:24])
                    ).Elif(data_length == 8,
                        NextState("READ")
                    )
                )
            )
        )

        fsm.act("READ",
            If(ch_sel,
                If(flags & SPI_END,
                    NextValue(self.ftw, current_data),
                    NextState("IDLE")
                )
            )
        )
