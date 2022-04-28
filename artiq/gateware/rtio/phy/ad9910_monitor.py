from migen import Signal, Array, If, Case

from artiq.coredevice.ad9910 import _AD9910_REG_PROFILE0, _AD9910_REG_PROFILE7, _AD9910_REG_FTW
from artiq.coredevice.spi2 import SPI_DATA_ADDR, SPI_END
from artiq.coredevice.urukul import CS_DDS_CH0
from artiq.gateware.rtio.phy.urukul_monitor import AD9910_AD9912MonitorGeneric


class AD9910Monitor(AD9910_AD9912MonitorGeneric):
    def __init__(self, spi_phy, io_update_phy, nchannels=4):
        data = [Signal(32) for i in range(nchannels)]
        buffer = [Signal(32) for i in range(nchannels)]

        # Flatten register first, then data
        self.probes = Array(data)
        super().__init__(spi_phy, io_update_phy)

        # 0 -> init, 1 -> start reading
        state = [Signal(1) for i in range(nchannels)]

        # Bit D0-D4: address, Bit D7: read/write
        reg = self.current_data[24:29]
        for i in range(nchannels):
            self.sync.rio_phy += If(self.selected(i + CS_DDS_CH0) & (self.current_address == SPI_DATA_ADDR), [
                Case(state[i], {
                    0: [
                        # not read
                        If(~self.current_data[31], [
                            If((_AD9910_REG_PROFILE0 <= reg) & (reg <= _AD9910_REG_PROFILE7), [
                                If(self.length == 8, [
                                    # assume it is write64, which means the last command in the SPI sequence (SPI_END)
                                    # will be FTW
                                    state[i].eq(1)
                                ])
                            ]).Elif(reg == _AD9910_REG_FTW, [
                                If((self.length == 24) & (self.flags & SPI_END), [
                                    # write16
                                    buffer[i][:16].eq(self.current_data[8:24]),
                                ]).Elif(self.length == 8, [
                                    # write32
                                    state[i].eq(1)
                                ])
                            ]),

                        ])
                    ],
                    1: [
                        If(self.flags & SPI_END, [
                            buffer[i][:32].eq(self.current_data),
                            state[i].eq(0)
                        ])
                    ]
                })
            ])

        self.sync.rio_phy += If(self.is_io_update(), [
            If(self.current_address == SPI_DATA_ADDR, [
                If(self.selected(i + CS_DDS_CH0), [
                    data[i].eq(buffer[i])
                ])
                for i in range(nchannels)
            ]),
            [state[i].eq(0) for i in range(nchannels)]
        ])