from migen import *

from artiq.coredevice.spi2 import SPI_CONFIG_ADDR, SPI_DATA_ADDR, SPI_END, SPI_INPUT
from artiq.coredevice.urukul import CS_DDS_CH0, CS_DDS_MULTI, CS_CFG, CFG_IO_UPDATE


class AD99XXMonitorGeneric(Module):
    def __init__(self, spi_phy, io_update_phy):
        self.spi_phy = spi_phy
        self.io_update_phy = io_update_phy

        self.current_address = Signal.like(self.spi_phy.rtlink.o.address)
        self.current_data = Signal.like(self.spi_phy.rtlink.o.data)
        self.cs = Signal(8)
        self.length = Signal(8)
        self.flags = Signal(8)

        self.sync.rio += If(self.spi_phy.rtlink.o.stb, [
            self.current_address.eq(self.spi_phy.rtlink.o.address),
            self.current_data.eq(self.spi_phy.rtlink.o.data),
            If(self.current_address == SPI_CONFIG_ADDR, [
                self.cs.eq(self.current_data[24:]),
                self.length.eq(self.current_data[8:16] + 1),
                self.flags.eq(self.current_data[0:8])
            ])
        ])

    def selected(self, c):
        return (self.cs == CS_DDS_MULTI) | (self.cs == c)

    def master_is_data_and_not_input(self):
        return (self.current_address == SPI_DATA_ADDR) & ~(self.flags & SPI_INPUT)

    def is_io_update(self):
        # shifted 8 bits left for 32-bit bus
        dest_cfg_reg_and_io_update_bit_set = self.cs == CS_CFG & self.current_data[8 + CFG_IO_UPDATE]
        if self.io_update_phy is not None and self.io_update_phy.rtlink is not None:
            io_update_strobe_set_and_high = self.io_update_phy.rtlink.o.stb & self.io_update_phy.rtlink.o.data
            return io_update_strobe_set_and_high | dest_cfg_reg_and_io_update_bit_set
        return dest_cfg_reg_and_io_update_bit_set


class AD9910Monitor(AD99XXMonitorGeneric):
    def __init__(self, spi_phy, io_update_phy, nchannels=4):
        data = [{'register': Signal(8), 'value': Signal(32)} for i in range(nchannels)]
        buffer = [{'register': Signal(8), 'value': Signal(32)} for i in range(nchannels)]

        # Flatten register first, then data
        self.probes = Array([
            *[x['register'] for x in data],
            *[x['value'] for x in data]
        ])
        super().__init__(spi_phy, io_update_phy)

        def update_probe_data(i):
            return If(self.selected(i + CS_DDS_CH0), [
                data[i]['value'].eq(buffer[i]['value']),
                data[i]['register'].eq(buffer[i]['register'])
            ])

        # 0 -> init, 1 -> has remaining part
        state = Signal()
        for i in range(nchannels):
            self.sync.rio_phy += If(self.selected(i + CS_DDS_CH0) & self.master_is_data_and_not_input(), [
                Case(state, {
                    0: [
                        If(self.length == 24 & (self.flags & SPI_END), [
                            # write16
                            buffer[i]['register'].eq(self.current_data[24:]),
                            buffer[i]['value'].eq(self.current_data[8:24]),
                        ]).Elif(self.length == 8, [
                            # write32
                            buffer[i]['register'].eq(self.current_data[24:]),
                            state.eq(1)
                        ])
                    ],
                    1: [
                        If(self.flags & SPI_END, buffer[i]['value'].eq(self.current_data))
                    ]
                })
            ])

        self.sync.rio_phy += If(self.is_io_update(), [
            state.eq(0),
            If(self.master_is_data_and_not_input(), [update_probe_data(i) for i in range(nchannels)])
        ])


class AD9912Monitor(AD99XXMonitorGeneric):
    def __init__(self, spi_phy, io_update_phy, nchannels=4):
        data = [
            {'register': Signal(24), 'value': Signal(48)} for i in range(nchannels)
        ]
        buffer = [
            {'register': Signal(24), 'value': Signal(48)} for i in range(nchannels)
        ]

        # Flatten register first, then data
        self.probes = Array([
            *[x['register'] for x in data],
            *[x['value'] for x in data]
        ])
        super().__init__(spi_phy, io_update_phy)

        def update_probe_data(i):
            return If(self.selected(i + CS_DDS_CH0), [
                data[i]['value'].eq(buffer[i]['value']),
                data[i]['register'].eq(buffer[i]['register'])
            ])

        # 0 -> init, 1 -> has remaining part
        state = Signal(1)

        for i in range(nchannels):
            self.sync.rio_phy += If(self.selected(i + CS_DDS_CH0) & self.master_is_data_and_not_input(), [
                Case(state, {
                    0: [
                        # write/set_mu
                        If(self.length == 16, [
                            buffer[i]['register'].eq(self.current_data[16:28]),
                            state.eq(1)
                        ])
                    ],
                    1: [
                        If(self.flags & SPI_END, [
                            buffer[i]['value'][:32].eq(self.current_data)
                        ]).Else([
                            buffer[i]['value'][32:48].eq(self.current_data[:16])
                        ])
                    ]
                })
            ])

        self.sync.rio_phy += If(self.is_io_update(), [
            state.eq(0),
            If(self.master_is_data_and_not_input(), [update_probe_data(i) for i in range(nchannels)])
        ])
