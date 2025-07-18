from artiq.experiment import *
from artiq.coredevice.spi2 import SPI_INPUT, SPI_END
from artiq.language.units import us, ms

class DAC_Init(EnvExperiment):
    MHz = 1e6

    def build(self):
        self.setattr_device("core")
        self.setattr_device("ttl0")
        self.setattr_device("ltc2000")
        self.setattr_device("spi_ltc")
        self.spi_config = SPI_END

    @kernel
    def run(self):
        self.core.reset()
        self.ttl0.output()
        self.ltc2000.initialize()
        self.verify_initialization()
        self.ltc2000.configure(100.0,0.0,0.0)

    @kernel
    def spi_write(self, addr, data):
        self.spi_ltc.set_config_mu(self.spi_config, 32, 256, 0b0001)
        delay(20*us)
        self.spi_ltc.write((addr << 24) | (data << 16))
        delay(2*us)
        self.spi_ltc.set_config_mu(self.spi_config, 32, 256, 0b0000)
        delay(20000*us)
        # print("SPI Write - Addr:", addr, "Data:", data)

    @kernel
    def spi_read(self, addr):
        self.spi_ltc.set_config_mu(self.spi_config | SPI_INPUT, 32, 256, 0b0001)
        delay(2*us)
        self.spi_ltc.write((1 << 31) | (addr << 24))
        delay(2*us)
        result = self.spi_ltc.read()
        delay(2*us)
        self.spi_ltc.set_config_mu(self.spi_config, 32, 256, 0b0000)
        delay(20000*us)
        value = (result >> 16) & 0xFF  # Extract the second most significant byte
        # print("SPI Read - Addr:", addr, "Value:", value)
        return value

    @kernel
    def initialize(self):
        self.spi_write(0x01, 0x00)  # Reset, power down controls
        self.spi_write(0x02, 0x00)  # Clock and DCKO controls
        self.spi_write(0x03, 0x01)  # DCKI controls
        self.spi_write(0x04, 0x0B)  # Data input controls
        self.spi_write(0x05, 0x00)  # Synchronizer controls
        self.spi_write(0x07, 0x00)  # Linearization controls
        self.spi_write(0x08, 0x08)  # Linearization voltage controls
        self.spi_write(0x18, 0x00)  # LVDS test MUX controls
        self.spi_write(0x19, 0x00)  # Temperature measurement controls
        self.spi_write(0x1E, 0x00)  # Pattern generator enable
        self.spi_write(0x1F, 0x00)  # Pattern generator data

    @kernel
    def verify_initialization(self):
        register_addresses = [1, 2, 3, 4, 5, 7, 8, 24, 25, 30]
        expected_values = [0, 0, 1, 11, 0, 0, 8, 0, 0, 0]
        for i in range(len(register_addresses)):
            addr = register_addresses[i]
            expected = expected_values[i]
            read_value = self.spi_read(addr)
            # delay(20*ms)
            if self.compare_values(read_value, expected) != 0:
                print("Warning: Register mismatch at address", addr)
                print("Register", addr, " - expected", expected, " - read", read_value)



    @kernel
    def compare_values(self, a: TInt32, b: TInt32) -> TInt32:
        if a < b:
            return -1
        elif a > b:
            return 1
        return 0