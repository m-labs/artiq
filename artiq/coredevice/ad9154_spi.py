from artiq.language.core import kernel


class AD9154:
    """Kernel interface to AD9154 registers, using non-realtime SPI."""

    def __init__(self, dmgr, spi_device, chip_select):
        self.core = dmgr.get("core")
        self.bus = dmgr.get(spi_device)
        self.chip_select = chip_select

    @kernel
    def setup_bus(self, div=16):
        self.bus.set_config_mu(0, 24, div, self.chip_select)

    @kernel
    def write(self, addr, data):
        self.bus.write((addr << 16) | (data<< 8))

    @kernel
    def read(self, addr):
        self.write((1 << 15) | addr, 0)
        return self.bus.read()
