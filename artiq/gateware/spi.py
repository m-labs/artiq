from itertools import product

from migen import *
from migen.genlib.fsm import *
from migen.genlib.misc import WaitTimer
from misoc.interconnect import wishbone


class SPIMaster(Module):
    """SPI Master.

    Notes:
        * M = 32 is the data width (width of the data register,
          maximum write bits, maximum read bits)
        * If there is a miso wire in pads, the input and output can be done
          with two signals (a.k.a. 4-wire SPI), else mosi must be used for
          both output and input (a.k.a. 3-wire SPI) and config.half_duplex
          needs to be set.
        * Every transfer consists of a 0-M bit write followed by a 0-M
          bit read.
        * cs_n is always asserted at the beginning and deasserted
          at the end of the transfer.
        * cs_n handling is agnostic to whether it is one-hot or decoded
          somewhere downstream. If it is decoded, "cs_n all deasserted"
          should be handled accordingly (no slave selected).
          If it is one-hot, asserting multiple slaves should only be attempted
          if miso is either not connected between slaves or open collector.
          cs can also be handled independently through other means.
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
        * Data output on mosi in 4-wire SPI during the read cycles is what
          is found in the data register at the time.
          Data in the data register outside the least/most (depending
          on config.lsb_first) significant read_len bits is what is
          seen on miso during the write cycles.
        * When the transfer is complete the wishbone transaction is ack-ed.
        * Input data from the last transaction can be read from the data
          register at any time.

    Transaction Sequence:
        * If desired, write the config register to set up the core.
        * If desired, write the xfer register to change lengths and cs_n.
        * Write the data register (also for zero-length writes),
          writing triggers the transfer and when the transfer is complete the
          write is ack-ed.
        * If desired, read the data register.

    Register address and bit map:

    config (address 2):
        1 offline: all pins high-z (reset=1)
        1 cs_polarity: active level of chip select (reset=0)
        1 clk_polarity: idle level for clk (reset=0)
        1 clk_phase: first edge after cs assertion to sample data on (reset=0)
            (0, 0): idle low, output on falling, input on rising
            (0, 1): idle low, output on rising, input on falling
            (1, 0): idle high, output on rising, input on falling
            (1, 1): idle high, output on falling, input on rising
        1 lsb_first: LSB is the first bit on the wire (reset=0)
        1 half_duplex: 3-wire SPI, in/out on mosi (reset=0)
        10 undefined
        16 clk_load: clock load value to divide from this module's clock
            to the SPI write clk clk pulses are asymmetric
            if a divider is odd, favoring longer setup over hold times.
            clk/spi_clk == clk_load + 2 (reset=0)

    xfer (address 1):
        16 cs: active high bit mask of chip selects to assert
        8 write_len: 0-M bits
        8 read_len: 0-M bits

    data (address 0):
        M write/read data
    """
    def __init__(self, pads, bus=None, data_width=32):
        if bus is None:
            bus = wishbone.Interface(data_width=data_width)
        self.bus = bus

        ###

        # State machine
        wb_we = Signal()
        start = Signal()
        active = Signal()

        fsm = FSM("IDLE")
        self.submodules += fsm

        fsm.act("IDLE",
            If(bus.cyc & bus.stb,
                NextState("ACK"),
                If(bus.we,
                    wb_we.eq(1),
                    If(bus.adr == 0,  # data register
                        NextState("START"),
                    )
                )
            )
        )
        fsm.act("START",
            start.eq(1),
            NextState("ACTIVE"),
        )
        fsm.act("ACTIVE",
            If(~active,
                bus.ack.eq(1),
                NextState("IDLE"),
            )
        )
        fsm.act("ACK",
            bus.ack.eq(1),
            NextState("IDLE"),
        )

        # Wishbone
        config = Record([
            ("offline", 1),
            ("cs_polarity", 1),
            ("clk_polarity", 1),
            ("clk_phase", 1),
            ("lsb_first", 1),
            ("half_duplex", 1),
            ("padding", 10),
            ("clk_load", 16),
        ])
        config.offline.reset = 1
        assert len(config) <= len(bus.dat_w)

        xfer = Record([
            ("cs", 16),
            ("write_length", 8),
            ("read_length", 8),
        ])
        assert len(xfer) <= len(bus.dat_w)

        data = Signal.like(bus.dat_w)

        wb_data = Array([data, xfer.raw_bits(), config.raw_bits()])[bus.adr]
        self.comb += bus.dat_r.eq(wb_data)
        self.sync += If(wb_we, wb_data.eq(bus.dat_w))

        # SPI
        write_count = Signal.like(xfer.write_length)
        read_count = Signal.like(xfer.read_length)
        clk_count = Signal.like(config.clk_load)
        clk = Signal(reset=1)  # idle high
        phase = Signal()
        edge = Signal()
        write = Signal()
        read = Signal()
        miso = Signal()
        miso_i = Signal()
        mosi_o = Signal()

        self.comb += [
            phase.eq(clk ^ config.clk_phase),
            edge.eq(active & (clk_count == 0)),
            write.eq(write_count != 0),
            read.eq(read_count != 0),
        ]

        self.sync += [
            If(start,
                write_count.eq(xfer.write_length),
                read_count.eq(xfer.read_length),
                active.eq(1),
            ),
            If(active,
                clk_count.eq(clk_count - 1),
            ),
            If(start | edge,
                # setup time passes during phase 0
                # use the lsb to bias that time to favor longer setup times
                clk_count.eq(config.clk_load[1:] +
                             (config.clk_load[0] & phase)),
                clk.eq(~clk),  # idle high
                If(phase,
                    data.eq(Mux(config.lsb_first,
                                Cat(data[1:], miso),
                                Cat(miso, data[:-1]))),
                    mosi_o.eq(Mux(config.lsb_first, data[0], data[-1])),
                    If(write,
                        write_count.eq(write_count - 1),
                    ),
                ).Else(
                    miso.eq(miso_i),
                    If(~write & read,
                        read_count.eq(read_count - 1),
                    ),
                ),
            ),
            If(~clk & edge & ~write & ~read,  # always from low clk
                active.eq(0),
            ),
        ]

        # I/O
        cs_n_t = TSTriple(len(pads.cs_n))
        self.specials += cs_n_t.get_tristate(pads.cs_n)
        clk_t = TSTriple()
        self.specials += clk_t.get_tristate(pads.clk)
        mosi_t = TSTriple()
        self.specials += mosi_t.get_tristate(pads.mosi)

        self.comb += [
            cs_n_t.oe.eq(~config.offline),
            clk_t.oe.eq(~config.offline),
            mosi_t.oe.eq(~config.offline & (write | ~config.half_duplex)),
            cs_n_t.o.eq((xfer.cs & Replicate(active, len(xfer.cs))) ^
                        Replicate(~config.cs_polarity, len(xfer.cs))),
            clk_t.o.eq((clk & active) ^ config.clk_polarity),
            miso_i.eq(Mux(config.half_duplex, mosi_t.i,
                          getattr(pads, "miso", mosi_t.i))),
            mosi_t.o.eq(mosi_o),
        ]


SPI_CONFIG_ADDR = 2
SPI_XFER_ADDR = 1
SPI_DATA_ADDR = 0
SPI_OFFLINE = 1 << 0
SPI_CS_POLARITY = 1 << 1
SPI_CLK_POLARITY = 1 << 2
SPI_CLK_PHASE = 1 << 3
SPI_LSB_FIRST = 1 << 4
SPI_HALF_DUPLEX = 1 << 5


def SPI_CLK_LOAD(i):
    return i << 16


def SPI_CS(i):
    return i << 0


def SPI_WRITE_LENGTH(i):
    return i << 16


def SPI_READ_LENGTH(i):
    return i << 24


def _test_gen(bus):
    yield from bus.write(SPI_CONFIG_ADDR,
                         1*SPI_CLK_PHASE | 0*SPI_LSB_FIRST |
                         1*SPI_HALF_DUPLEX | SPI_CLK_LOAD(3))
    yield
    yield from bus.write(SPI_XFER_ADDR, SPI_CS(0b00001) |
                         SPI_WRITE_LENGTH(4) | SPI_READ_LENGTH(0))
    yield
    yield from bus.write(SPI_DATA_ADDR, 0x90000000)
    yield
    print(hex((yield from bus.read(SPI_DATA_ADDR))))
    yield
    yield from bus.write(SPI_XFER_ADDR, SPI_CS(0b00010) |
                         SPI_WRITE_LENGTH(4) | SPI_READ_LENGTH(4))
    yield
    yield from bus.write(SPI_DATA_ADDR, 0x81000000)
    yield
    print(hex((yield from bus.read(SPI_DATA_ADDR))))
    yield
    yield from bus.write(SPI_XFER_ADDR, SPI_CS(0b00010) |
                         SPI_WRITE_LENGTH(0) | SPI_READ_LENGTH(4))
    yield
    yield from bus.write(SPI_DATA_ADDR, 0x90000000)
    yield
    print(hex((yield from bus.read(SPI_DATA_ADDR))))
    yield
    yield from bus.write(SPI_XFER_ADDR, SPI_CS(0b00010) |
                         SPI_WRITE_LENGTH(32) | SPI_READ_LENGTH(0))
    yield
    yield from bus.write(SPI_DATA_ADDR, 0x87654321)
    yield
    print(hex((yield from bus.read(SPI_DATA_ADDR))))
    yield

    return
    for cpol, cpha, lsb, clk in product(
            (0, 1), (0, 1), (0, 1), (0, 1)):
        yield from bus.write(SPI_CONFIG_ADDR,
                             cpol*SPI_CLK_POLARITY | cpha*SPI_CLK_PHASE |
                             lsb*SPI_LSB_FIRST | SPI_CLK_LOAD(clk))
        for wlen, rlen, wdata in product((0, 8, 32), (0, 8, 32),
                                         (0, 0xffffffff, 0xdeadbeef)):
            yield from bus.write(SPI_XFER_ADDR, SPI_CS(0b00001) |
                                 SPI_WRITE_LENGTH(wlen) |
                                 SPI_READ_LENGTH(rlen))
            yield from bus.write(SPI_DATA_ADDR, wdata)
            rdata = yield from bus.read(SPI_DATA_ADDR)
            len = (wlen + rlen) % 32
            mask = (1 << len) - 1
            if lsb:
                shift = (wlen + rlen) % 32
            else:
                shift = 0
            a = (wdata >> wshift) & wmask
            b = (rdata >> rshift) & rmask
            if a != b:
                print("ERROR", end=" ")
            print(cpol, cpha, lsb, clk, wlen, rlen,
                  hex(wdata), hex(rdata), hex(a), hex(b))



class _TestPads:
    def __init__(self):
        self.cs_n = Signal(3)
        self.clk = Signal()
        self.mosi = Signal()
        self.miso = Signal()


if __name__ == "__main__":
    from migen.fhdl.specials import Tristate

    class T(Module):
        def __init__(self, t):
            oe = Signal()
            self.comb += [
                t.target.eq(t.o),
                oe.eq(t.oe),
                t.i.eq(t.o),
            ]
    Tristate.lower = staticmethod(lambda dr: T(dr))

    from migen.fhdl.verilog import convert
    pads = _TestPads()
    dut = SPIMaster(pads)
    dut.comb += pads.miso.eq(pads.mosi)
    #print(convert(dut))

    run_simulation(dut, _test_gen(dut.bus), vcd_name="spi_master.vcd")
