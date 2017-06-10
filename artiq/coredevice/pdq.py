from artiq.language.core import kernel, portable, delay_mu
from artiq.coredevice import spi
from artiq.devices.pdq.protocol import PDQBase, PDQ_CMD


_PDQ_SPI_CONFIG = (
        0*spi.SPI_OFFLINE | 0*spi.SPI_CS_POLARITY |
        0*spi.SPI_CLK_POLARITY | 0*spi.SPI_CLK_PHASE |
        0*spi.SPI_LSB_FIRST | 0*spi.SPI_HALF_DUPLEX
        )



class PDQ(PDQBase):
    """PDQ smart arbitrary waveform generator stack.

    Provides access to a stack of PDQ boards connected via SPI using PDQ
    gateware version 3 or later.

    The SPI bus is wired with ``CS_N`` from the core device connected to
    ``F2 IN`` on the master PDQ, ``CLK`` connected to ``F3 IN``, ``MOSI``
    connected to ``F4 IN`` and ``MISO`` (optionally) connected to ``F5 OUT``.
    ``F1 TTL Input Trigger`` remains as waveform trigger input.
    Due to hardware constraints, there can only be one board connected to the
    core device's MISO line and therefore there can only be SPI readback
    from one board at any time.

    :param spi_device: Name of the SPI bus this device is on.
    :param chip_select: Value to drive on the chip select lines of the SPI bus
        during transactions.
    """

    kernel_invariants = {"core", "chip_select", "bus"}

    def __init__(self, dmgr, spi_device, chip_select=1, **kwargs):
        self.core = dmgr.get("core")
        self.bus = dmgr.get(spi_device)
        self.chip_select = chip_select
        PDQBase.__init__(self, **kwargs)

    @kernel
    def setup_bus(self, write_div=24, read_div=64):
        """Configure the SPI bus and the SPI transaction parameters
        for this device. This method has to be called before any other method
        if the bus has been used to access a different device in the meantime.

        This method advances the timeline by the duration of two
        RTIO-to-Wishbone bus transactions.

        :param write_div: Write clock divider.
        :param read_div: Read clock divider.
        """
        # write: 4*8ns >= 20ns = 2*clk (clock de-glitching 50MHz)
        # read: 15*8*ns >= ~100ns = 5*clk (clk de-glitching latency + miso
        #   latency)
        self.bus.set_config_mu(_PDQ_SPI_CONFIG, write_div, read_div)
        self.bus.set_xfer(self.chip_select, 16, 0)

    @kernel
    def write_reg(self, adr, data, board):
        """Set a PDQ register.

        :param adr: Address of the register (``_PDQ_ADR_CONFIG``,
            ``_PDQ_ADR_FRAME``, ``_PDQ_ADR_CRC``).
        :param data: Register data (8 bit).
        :param board: Board to access, ``0xf`` to write to all boards.
        """
        self.bus.write((PDQ_CMD(board, 0, adr, 1) << 24) | (data << 16))
        delay_mu(self.bus.ref_period_mu)  # get to 20ns min cs high

    @kernel
    def read_reg(self, adr, board):
        """Get a PDQ register.

        :param adr: Address of the register (``_PDQ_ADR_CONFIG``,
          ``_PDQ_ADR_FRAME``, ``_PDQ_ADR_CRC``).
        :param board: Board to access, ``0xf`` to write to all boards.

        :return: Register data (8 bit).
        """
        self.bus.set_xfer(self.chip_select, 16, 8)
        self.bus.write(PDQ_CMD(board, 0, adr, 0) << 24)
        delay_mu(self.bus.ref_period_mu)  # get to 20ns min cs high
        self.bus.read_async()
        self.bus.set_xfer(self.chip_select, 16, 0)
        return int(self.bus.input_async() & 0xff)  # FIXME: m-labs/artiq#713

    @kernel
    def write_mem(self, mem, adr, data, board=0xf):  # FIXME: m-labs/artiq#714
        """Write to DAC channel waveform data memory.

        :param mem: DAC channel memory to access (0 to 2).
        :param adr: Start address.
        :param data: Memory data. List of 16 bit integers.
        :param board: Board to access (0-15) with ``0xf = 15`` being broadcast
            to all boards.
        """
        self.bus.set_xfer(self.chip_select, 24, 0)
        self.bus.write((PDQ_CMD(board, 1, mem, 1) << 24) |
                       ((adr & 0x00ff) << 16) | (adr & 0xff00))
        delay_mu(-self.bus.write_period_mu-3*self.bus.ref_period_mu)
        self.bus.set_xfer(self.chip_select, 16, 0)
        for i in data:
            self.bus.write(i << 16)
            delay_mu(-self.bus.write_period_mu)
        delay_mu(self.bus.write_period_mu + self.bus.ref_period_mu)
        # get to 20ns min cs high

    @kernel
    def read_mem(self, mem, adr, data, board=0xf, buffer=8):
        """Read from DAC channel waveform data memory.

        :param mem: DAC channel memory to access (0 to 2).
        :param adr: Start address.
        :param data: Memory data. List of 16 bit integers.
        :param board: Board to access (0-15) with ``0xf = 15`` being broadcast
            to all boards.
        """
        n = len(data)
        if not n:
            return
        self.bus.set_xfer(self.chip_select, 24, 8)
        self.bus.write((PDQ_CMD(board, 1, mem, 0) << 24) |
                       ((adr & 0x00ff) << 16) | (adr & 0xff00))
        delay_mu(-self.bus.write_period_mu-3*self.bus.ref_period_mu)
        self.bus.set_xfer(self.chip_select, 0, 16)
        for i in range(n):
            self.bus.write(0)
            delay_mu(-self.bus.write_period_mu)
            if i > 0:
                delay_mu(-3*self.bus.ref_period_mu)
                self.bus.read_async()
            if i > buffer:
                data[i - 1 - buffer] = self.bus.input_async() & 0xffff
        delay_mu(self.bus.write_period_mu)
        self.bus.set_xfer(self.chip_select, 16, 0)
        self.bus.read_async()
        for i in range(max(0, n - buffer - 1), n):
            data[i] = self.bus.input_async() & 0xffff
