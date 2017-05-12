from artiq.language.core import kernel, portable, delay_mu
from artiq.coredevice import spi


_PDQ_SPI_CONFIG = (
        0*spi.SPI_OFFLINE | 0*spi.SPI_CS_POLARITY |
        0*spi.SPI_CLK_POLARITY | 0*spi.SPI_CLK_PHASE |
        0*spi.SPI_LSB_FIRST | 0*spi.SPI_HALF_DUPLEX
        )


@portable
def _PDQ_CMD(board, is_mem, adr, we):
    """Pack PDQ command fields into command byte.

    :param board: Board address, 0 to 15, with ``15 = 0xf`` denoting broadcast
        to all boards connected.
    :param is_mem: If ``1``, ``adr`` denote the address of the memory to access
        (0 to 2). Otherwise ``adr`` denotes the register to access.
    :param adr: Address of the register or memory to access.
        (``_PDQ_ADR_CONFIG``, ``_PDQ_ADR_FRAME``, ``_PDQ_ADR_CRC``).
    :param we: If ``1`` then write, otherwise read.
    """
    return (adr << 0) | (is_mem << 2) | (board << 3) | (we << 7)


_PDQ_ADR_CONFIG = 0
_PDQ_ADR_CRC = 1
_PDQ_ADR_FRAME = 2


class PDQ:
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

    def __init__(self, dmgr, spi_device, chip_select=1):
        self.core = dmgr.get("core")
        self.bus = dmgr.get(spi_device)
        self.chip_select = chip_select

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
        self.bus.write((_PDQ_CMD(board, 0, adr, 1) << 24) | (data << 16))
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
        self.bus.write(_PDQ_CMD(board, 0, adr, 0) << 24)
        delay_mu(self.bus.ref_period_mu)  # get to 20ns min cs high
        self.bus.read_async()
        self.bus.set_xfer(self.chip_select, 16, 0)
        return int(self.bus.input_async() & 0xff)  # FIXME: m-labs/artiq#713

    @kernel
    def write_config(self, reset=0, clk2x=0, enable=1,
                     trigger=0, aux_miso=0, aux_dac=0b111, board=0xf):
        """Set configuration register.

        :param reset: Reset board (auto-clear).
        :param clk2x: Enable clock double (100 MHz).
        :param enable: Enable the reading and execution of waveform data from
            memory.
        :param trigger: Software trigger, logical OR with ``F1 TTL Input
            Trigger``.
        :param aux_miso: Use ``F5 OUT`` for ``MISO``. If ``0``, use the
            masked logical OR of the DAC channels.
        :param aux_dac: DAC channel mask to for AUX (``F5 OUT``) output.
        :param board: Boards to address, ``0xf`` to write to all boards.
        """
        config = ((reset << 0) | (clk2x << 1) | (enable << 2) |
                  (trigger << 3) | (aux_miso << 4) | (aux_dac << 5))
        self.write_reg(_PDQ_ADR_CONFIG, config, board)

    @kernel
    def read_config(self, board=0xf):
        """Read configuration register."""
        return self.read_reg(_PDQ_ADR_CONFIG, board)

    @kernel
    def write_crc(self, crc, board=0xf):
        """Write checksum register."""
        self.write_reg(_PDQ_ADR_CRC, crc, board)

    @kernel
    def read_crc(self, board=0xf):
        """Read checksum register."""
        return self.read_reg(_PDQ_ADR_CRC, board)

    @kernel
    def write_frame(self, frame, board=0xf):
        """Write frame selection register."""
        self.write_reg(_PDQ_ADR_FRAME, frame, board)

    @kernel
    def read_frame(self, board=0xf):
        """Read frame selection register."""
        return self.read_reg(_PDQ_ADR_FRAME, board)

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
        self.bus.write((_PDQ_CMD(board, 1, mem, 1) << 24) |
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
        self.bus.write((_PDQ_CMD(board, 1, mem, 0) << 24) |
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
