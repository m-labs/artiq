from migen import *

from artiq.coredevice.spi2 import SPI_CONFIG_ADDR, SPI_DATA_ADDR, SPI_END, SPI_INPUT
from artiq.coredevice.urukul import CS_DDS_CH0, CS_DDS_MULTI


class AD99XXMonitorGeneric(Module):
    def __init__(self, spi_rtlink):
        self.rtlink = spi_rtlink

        self.current_address = Signal.like(self.rtlink.o.address)
        self.current_data = Signal.like(self.rtlink.o.data)
        self.sync.rio += If(
            self.rtlink.o.stb,
            self.current_address.eq(self.rtlink.o.address),
            self.current_data.eq(self.rtlink.o.data)
        )

        self.cs = Signal(8)
        self.length = Signal(8)
        self.flags = Signal(8)

        self.sync.rio += If(
            self.rtlink.o.stb & (self.current_address == SPI_CONFIG_ADDR),
            self.cs.eq(self.current_data[24:]),
            # self.div.eq(self.current_data[16:24] + 2),
            self.length.eq(self.current_data[8:16] + 1),
            self.flags.eq(self.current_data[0:8])
        )

    def selected(self, c):
        if self.cs == CS_DDS_MULTI:
            return True
        else:
            return c == self.cs

    def master_is_data_and_not_input(self):
        return (self.current_address == SPI_DATA_ADDR) & ~(self.flags & SPI_INPUT)


class AD9910Monitor(AD99XXMonitorGeneric):
    def __init__(self, spi_rtlink, phy, nchannels=4):
        data = [{'register': Signal(8), 'value': Signal(32)} for i in range(nchannels)]
        buffer = [{'register': Signal(8), 'value': Signal(32)} for i in range(nchannels)]

        # Flatten register first, then data
        self.probes = Array([
            *[x['register'] for x in data],
            *[x['value'] for x in data]
        ])
        super().__init__(spi_rtlink)

        # 0 -> init, 1 -> start read value
        state = Signal()
        for i in range(nchannels):
            self.sync.rio_phy += If(
                self.selected(i + CS_DDS_CH0) & (self.current_address == SPI_DATA_ADDR) & ~(self.flags & SPI_INPUT), [
                    Case(state, {
                        0: [
                            # write16
                            If(self.length == 24 & (self.flags & SPI_END), [
                                buffer[i]['register'].eq((self.current_data >> 24) & 0xff),
                                buffer[i]['value'].eq((self.current_data >> 8) & 0xffff),
                            ]).
                             # write32
                             Elif(self.length == 8, [
                                buffer[i]['register'].eq((self.current_data >> 24) & 0xff),
                                state.eq(1)
                            ])
                        ],
                        1: [
                            If(self.flags & SPI_END, buffer[i]['value'].eq(self.current_data))
                        ]
                    })
                ])

        self.sync.rio_phy += If(phy.rtlink.o.stb, [
            state.eq(0),
            If(self.master_is_data_and_not_input(), [
                If(self.selected(i + CS_DDS_CH0), [
                    data[i]['value'].eq(buffer[i]['value']),
                    data[i]['register'].eq(buffer[i]['register'])
                ]) for i in range(nchannels)
            ])
        ])


class AD9912Monitor(AD99XXMonitorGeneric):
    def __init__(self, spi_rtlink, phy, nchannels=4):
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
        super().__init__(spi_rtlink)

        # 0 -> init, 1 -> start read value
        state = Signal(1)

        for i in range(nchannels):
            self.sync.rio_phy += If(
                self.selected(i + CS_DDS_CH0) & (self.current_address == SPI_DATA_ADDR) & ~(self.flags & SPI_INPUT), [
                    Case(state, {
                        0: [
                            # write/set_mu
                            If(self.length == 16, [
                                buffer[i]['register'].eq(self.current_data[16:28]),
                                state.eq(1)
                            ])
                        ],
                        1: [
                            If(self.flags & SPI_END, buffer[i]['value'][:32].eq(self.current_data)).
                            Else(buffer[i]['value'][32:48].eq(self.current_data[:16]))
                        ]
                    })
                ])

        self.sync.rio_phy += If(phy.rtlink.o.stb, [
            state.eq(0),
            If(self.master_is_data_and_not_input(), [
                If(self.selected(i + CS_DDS_CH0), [
                    data[i]['register'].eq(buffer[i]['register']),
                    data[i]['value'].eq(buffer[i]['value'])
                ]) for i in range(nchannels)
            ])
        ])
