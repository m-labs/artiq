from migen import *
from migen.genlib.fsm import *
from migen.genlib.misc import WaitTimer
from misoc.interconnect import wishbone


class SPIMaster(Module):
    """SPI Master.

    Notes:
        * If there is a miso wire in pads, the input and output are done with
          two signals (a.k.a. 4-wire SPI), else mosi is used for both output
          and input (a.k.a. 3-wire SPI).
        * Every transfer consists of a 0-32 bit write followed by a 0-32
          bit read.
        * cs_n is always asserted at the beginning and deasserted
          at the end of the tranfer.
        * cs_n handling is agnostic to whether it is one-hot or decoded
          somewhere downstream. If it is decoded, "cs_n all deasserted"
          should be handled accordingly (no slave selected).
          If it is one-hot, asserting multiple slaves should only be attempted
          if miso is either not connected between slaves or open collector.
        * If config.cs_polarity == 0 (cs active low, the default),
          "cs_n all deasserted" means "all cs_n bits high".
        * The first bit output on mosi is always the MSB/LSB (depending on
          config.lsb_first) of the data register, independent of
          xfer.write_len. The last bit input from miso always ends up in
          the LSB/MSB (respectively) of the data register, independent of
          read_len.
        * For 4-wire SPI only the sum of read_len and write_len matters. The
          behavior is the same no matter how the transfer length is divided
          between the two. For 3-wire SPI, the direction of mosi/miso is
          switched from output to input after write_len cycles, at the
          "output" clk edge corresponding to bit write_len + 1 of the transfer.
        * Data output on mosi in 4-wire SPI during the read cycles is
          undefined. Data in the data register outside the
          least/most (depending on config.lsb_first) significant read_len
          bits is undefined.
        * The transfer is complete when the wishbone transaction is ack-ed.
        * Input data from the last transaction can be read from the data
          register at any time.

    Transaction Sequence:
        * if desired, write the xfer register to change lengths and cs_n.
        * write the data register (also for zero-length writes),
          writing triggers the transfer and the transfer is complete when the
          write is complete.
        * if desired, read the data register

    Register address and bit map:

    config (address 0):
        1 offline: all pins high-z (reset=1)
        1 cs_polarity: active level of chip select (reset=0)
        1 clk_polarity: idle level for clk (reset=0)
        1 clk_phase: first edge after cs assertion to sample data on (reset=0)
            (0, 0): idle low, output on falling, input on rising
            (0, 1): idle low, output on rising, input on falling
            (1, 0): idle high, output on rising, input on falling
            (1, 1): idle high, output on falling, input on rising
        1 lsb_first: LSB is the first bit on the wire (reset=0)
        11 undefined
        16 speed: divider from this module's clock to the SPI clk
            (minimum=2, reset=4)
            clk pulses are asymmetric if speed is odd, favoring longer setup
            over hold times

    xfer (address 1):
        16 cs: active high bit mask of chip selects to assert
        6 write_len: 0-32 bits
        2 undefined
        6 read_len: 0-32 bits
        2 undefined

    data (address 2):
        32 write/read data
    """
    def __init__(self, pads, bus=None):
        if bus is None:
            bus = wishbone.Interface(data_width=32)
        self.bus = bus

        ###


def _test_gen(bus):
    yield from bus.write(0, 0 | (5 << 16))
    yield
    yield from bus.write(1, 1 | (24 << 16) | (16 << 24))
    yield
    yield from bus.write(2, 0x12345678)
    yield
    r = (yield from bus.read(2))
    print(r)
    yield


class _TestPads:
    def __init__(self):
        self.cs_n = Signal(3)
        self.clk = Signal()
        self.mosi = Signal()
        self.miso = Signal()


if __name__ == "__main__":
    pads = _TestPads()
    dut = SPIMaster(pads)
    run_simulation(dut, _test_gen(dut.bus), vcd_name="spi_master.vcd")
