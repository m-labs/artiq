from artiq.experiment import *
from artiq.coredevice.spi2 import SPI_INPUT, SPI_END
from artiq.language.units import us, ms

class DAC_Init(EnvExperiment):
    MHz = 1e6

    def build(self):
        self.setattr_device("core")
        self.setattr_device("spi_ltc")
        self.setattr_device("ltc_clear")
        self.setattr_device("ltc_reset")
        self.spi_config = SPI_END

    @kernel
    def run(self):
        self.core.reset()
        delay(20000*us)
        self.ltc_clear.clear(0b1111)
        self.ltc_reset.reset(1)
        print("Performing software reset...")
        self.spi_write(0x01, 0x01)  # Write 1 to the reset bit
        delay(10*ms)  # Wait for reset to complete
        self.spi_write(0x01, 0x00)  # Clear the reset bit
        delay(20000*us)
        print("Initializing the LTC2000...")
        self.initialize()
        print("Verifying initialization...")
        self.verify_initialization()
        self.ltc_reset.reset(0)
        delay(20000*us)
        self.ltc_clear.clear(0)

    @kernel
    def spi_write(self, addr, data):
        self.bus.set_config_mu(self.spi_config, 32, 256, 0b0001)
        delay(20*us)
        self.bus.write((addr << 24) | (data << 16))
        delay(2*us)
        self.bus.set_config_mu(self.spi_config, 32, 256, 0b0000)

    @kernel
    def spi_read(self, addr):
        self.bus.set_config_mu(self.spi_config | SPI_INPUT, 32, 256, 0b0001)
        delay(2*us)
        self.bus.write((1 << 31) | (addr << 24))
        delay(2*us)
        result = self.spi_ltc.read()
        delay(2*us)
        self.bus.set_config_mu(self.spi_config, 32, 256, 0b0000)
        value = (result >> 16) & 0xFF  # Extract the second most significant byte
        return value

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
        register_expected_pairs = [
            (1, [0]),       # Register 1
            (2, [2]),       # Register 2
            (3, [3]),       # Register 3
            (4, [11]),      # Register 4
            (5, [0, 1, 2, 3]),  # Register 5 can be 0, 1, 2, or 3
            (7, [0]),       # Register 7
            (8, [8]),       # Register 8
            (24, [0]),      # Register 24
            (25, [0]),      # Register 25
            (30, [0]),      # Register 30
            (31, [0])       # Register 31
        ]

        VERBOSE = True
        for addr, expected in register_expected_pairs:
            read_value = self.spi_read(addr)
            if VERBOSE:
                print("Register", addr, " - expected one of", expected, " - read", read_value)
            if read_value not in expected:
                print("Warning: Register mismatch at address", addr)
                print("Register", addr, " - expected one of", expected, " - read", read_value)



    @kernel
    def compare_values(self, a: TInt32, b: TInt32) -> TInt32:
        if a < b:
            return -1
        elif a > b:
            return 1
        return 0