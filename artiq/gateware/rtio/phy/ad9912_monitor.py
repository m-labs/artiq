from migen import Signal, Array, If, Case

from artiq.coredevice.ad9912_reg import AD9912_FTW0, AD9912_POW1
from artiq.coredevice.spi2 import SPI_DATA_ADDR, SPI_END
from artiq.coredevice.urukul import CS_DDS_CH0
from artiq.gateware.rtio.phy.urukul_monitor import AD9910_AD9912MonitorGeneric


class AD9912Monitor(AD9910_AD9912MonitorGeneric):
    def __init__(self, spi_phy, io_update_phy, nchannels=4):
        data = [Signal(48) for i in range(nchannels)]
        buffer = [Signal(48) for i in range(nchannels)]

        # Flatten register first, then data
        self.probes = Array(data)
        super().__init__(spi_phy, io_update_phy)

        def update_probe_data(i):
            return If(self.selected(i + CS_DDS_CH0), [
                data[i].eq(buffer[i])
            ])

        # 0 -> init, 1 -> start reading
        state = [Signal(1) for i in range(nchannels)]

        reg = self.current_data[16:29]
        for i in range(nchannels):
            self.sync.rio_phy += If(self.selected(i + CS_DDS_CH0) & (self.current_address == SPI_DATA_ADDR), [
                Case(state[i], {
                    0: [
                        # Bits A0-A12: address, Bit D15: read write, total 16 bits, need to pad 16 bits
                        If((self.length == 16) & (AD9912_FTW0 <= reg) & (reg <= AD9912_POW1) & ~self.current_data[31], [
                            state[i].eq(1)
                        ])
                    ],
                    1: [
                        If(self.flags & SPI_END, [
                            buffer[i][:32].eq(self.current_data),
                            state[i].eq(0)
                        ]).Else([
                            buffer[i][32:].eq(self.current_data[:16])
                        ])
                    ]
                })
            ])

        self.sync.rio_phy += If(self.is_io_update(), [
            If(self.current_address == SPI_DATA_ADDR, [update_probe_data(i) for i in range(nchannels)]),
            [state[i].eq(0) for i in range(nchannels)]
        ])