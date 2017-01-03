from itertools import product

from migen import *
from misoc.interconnect import wishbone
from misoc.cores.spi import SPIMachine


class SPIMaster(Module):
    """SPI Master.

    Notes:
        * M = 32 is the data width (width of the data register,
          maximum write bits, maximum read bits)
        * Every transfer consists of a write_length 0-M bit write followed
          by a read_length 0-M bit read.
        * cs_n is asserted at the beginning and deasserted at the end of the
          transfer if there is no other transfer pending.
        * cs_n handling is agnostic to whether it is one-hot or decoded
          somewhere downstream. If it is decoded, "cs_n all deasserted"
          should be handled accordingly (no slave selected).
          If it is one-hot, asserting multiple slaves should only be attempted
          if miso is either not connected between slaves, or open collector,
          or correctly multiplexed externally.
        * If config.cs_polarity == 0 (cs active low, the default),
          "cs_n all deasserted" means "all cs_n bits high".
        * cs is not mandatory in pads. Framing and chip selection can also
          be handled independently through other means.
        * If there is a miso wire in pads, the input and output can be done
          with two signals (a.k.a. 4-wire SPI), else mosi must be used for
          both output and input (a.k.a. 3-wire SPI) and config.half_duplex
          must to be set when reading data is desired.
        * For 4-wire SPI only the sum of read_length and write_length matters.
          The behavior is the same no matter how the total transfer length is
          divided between the two. For 3-wire SPI, the direction of mosi/miso
          is switched from output to input after write_len cycles, at the
          "shift_out" clk edge corresponding to bit write_length + 1 of the
          transfer.
        * The first bit output on mosi is always the MSB/LSB (depending on
          config.lsb_first) of the data register, independent of
          xfer.write_len. The last bit input from miso always ends up in
          the LSB/MSB (respectively) of the data register, independent of
          read_len.
        * Data output on mosi in 4-wire SPI during the read cycles is what
          is found in the data register at the time.
          Data in the data register outside the least/most (depending
          on config.lsb_first) significant read_length bits is what is
          seen on miso during the write cycles.
        * The SPI data register is double-buffered: Once a transfer has
          started, new write data can be written, queuing a new transfer.
          Transfers submitted this way are chained and executed without
          deasserting cs. Once a transfer completes, the previous transfer's
          read data is available in the data register.
        * Writes to the config register take effect immediately. Writes to xfer
          and data are synchronized to the start of a transfer.
        * A wishbone data register write is ack-ed when the transfer has
          been written to the intermediate buffer. It will be started when
          there are no other transactions being executed, either starting
          a new SPI transfer of chained to an in-flight transfer.
          Writes take two cycles unless the write is to the data register
          and another chained transfer is pending and the transfer being
          executed is not complete. Reads always finish in two cycles.

    Transaction Sequence:
        * If desired, write the config register to set up the core.
        * If desired, write the xfer register to change lengths and cs_n.
        * Write the data register (also for zero-length writes),
          writing triggers the transfer and when the transfer is accepted to
          the inermediate buffer, the write is ack-ed.
        * If desired, read the data register corresponding to the last
          completed transfer.
        * If desired, change xfer register for the next transfer.
        * If desired, write data queuing the next (possibly chained) transfer.

    Register address and bit map:

    config (address 2):
        1 offline: all pins high-z (reset=1)
        1 active: cs/transfer active (read-only)
        1 pending: transfer pending in intermediate buffer (read-only)
        1 cs_polarity: active level of chip select (reset=0)
        1 clk_polarity: idle level of clk (reset=0)
        1 clk_phase: first edge after cs assertion to sample data on (reset=0)
            (clk_polarity, clk_phase) == (CPOL, CPHA) in Freescale language.
            (0, 0): idle low, output on falling, input on rising
            (0, 1): idle low, output on rising, input on falling
            (1, 0): idle high, output on rising, input on falling
            (1, 1): idle high, output on falling, input on rising
            There is never a clk edge during a cs edge.
        1 lsb_first: LSB is the first bit on the wire (reset=0)
        1 half_duplex: 3-wire SPI, in/out on mosi (reset=0)
        8 undefined
        8 div_write: counter load value to divide this module's clock
            to generate the SPI write clk (reset=0)
            f_clk/f_spi_write == div_write + 2
        8 div_read: ditto for the read clock

    xfer (address 1):
        16 cs: active high bit mask of chip selects to assert (reset=0)
        6 write_len: 0-M bits (reset=0)
        2 undefined
        6 read_len: 0-M bits (reset=0)
        2 undefined

    data (address 0):
        M write/read data (reset=0)
    """
    def __init__(self, pads, bus=None):
        if bus is None:
            bus = wishbone.Interface(data_width=32)
        self.bus = bus

        ###

        # Wishbone
        config = Record([
            ("offline", 1),
            ("active", 1),
            ("pending", 1),
            ("cs_polarity", 1),
            ("clk_polarity", 1),
            ("clk_phase", 1),
            ("lsb_first", 1),
            ("half_duplex", 1),
            ("padding", 8),
            ("div_write", 8),
            ("div_read", 8),
        ])
        config.offline.reset = 1
        assert len(config) <= len(bus.dat_w)

        xfer = Record([
            ("cs", 16),
            ("write_length", 6),
            ("padding0", 2),
            ("read_length", 6),
            ("padding1", 2),
        ])
        assert len(xfer) <= len(bus.dat_w)

        self.submodules.spi = spi = SPIMachine(
            data_width=len(bus.dat_w) + 1,
            clock_width=len(config.div_read),
            bits_width=len(xfer.read_length))

        pending = Signal()
        cs = Signal.like(xfer.cs)
        data_read = Signal.like(spi.reg.data)
        data_write = Signal.like(spi.reg.data)

        self.comb += [
            spi.start.eq(pending & (~spi.cs | spi.done)),
            spi.clk_phase.eq(config.clk_phase),
            spi.reg.lsb.eq(config.lsb_first),
            spi.div_write.eq(config.div_write),
            spi.div_read.eq(config.div_read),
        ]
        self.sync += [
            If(spi.done,
                data_read.eq(
                    Mux(spi.reg.lsb, spi.reg.data[1:], spi.reg.data[:-1])),
            ),
            If(spi.start,
                cs.eq(xfer.cs),
                spi.bits.n_write.eq(xfer.write_length),
                spi.bits.n_read.eq(xfer.read_length),
                If(spi.reg.lsb,
                    spi.reg.data[:-1].eq(data_write),
                ).Else(
                    spi.reg.data[1:].eq(data_write),
                ),
                pending.eq(0),
            ),
            # wb.ack a transaction if any of the following:
            # a) reading,
            # b) writing to non-data register
            # c) writing to data register and no pending transfer
            # d) writing to data register and pending and swapping buffers
            bus.ack.eq(bus.cyc & bus.stb &
                       (~bus.we | (bus.adr != 0) | ~pending | spi.done)),
            If(bus.cyc & bus.stb,
                bus.dat_r.eq(
                    Array([data_read, xfer.raw_bits(), config.raw_bits()
                           ])[bus.adr]),
            ),
            If(bus.ack,
                bus.ack.eq(0),
                If(bus.we,
                    Array([data_write, xfer.raw_bits(), config.raw_bits()
                          ])[bus.adr].eq(bus.dat_w),
                    If(bus.adr == 0,  # data register
                        pending.eq(1),
                    ),
                ),
            ),
            config.active.eq(spi.cs),
            config.pending.eq(pending),
        ]

        # I/O
        if hasattr(pads, "cs_n"):
            cs_n_t = TSTriple(len(pads.cs_n))
            self.specials += cs_n_t.get_tristate(pads.cs_n)
            self.comb += [
                cs_n_t.oe.eq(~config.offline),
                cs_n_t.o.eq((cs & Replicate(spi.cs, len(cs))) ^
                            Replicate(~config.cs_polarity, len(cs))),
            ]

        clk_t = TSTriple()
        self.specials += clk_t.get_tristate(pads.clk)
        self.comb += [
            clk_t.oe.eq(~config.offline),
            clk_t.o.eq((spi.cg.clk & spi.cs) ^ config.clk_polarity),
        ]

        mosi_t = TSTriple()
        self.specials += mosi_t.get_tristate(pads.mosi)
        self.comb += [
            mosi_t.oe.eq(~config.offline & spi.cs &
                         (spi.oe | ~config.half_duplex)),
            mosi_t.o.eq(spi.reg.o),
            spi.reg.i.eq(Mux(config.half_duplex, mosi_t.i,
                             getattr(pads, "miso", mosi_t.i))),
        ]


SPI_DATA_ADDR, SPI_XFER_ADDR, SPI_CONFIG_ADDR = range(3)
(
    SPI_OFFLINE,
    SPI_ACTIVE,
    SPI_PENDING,
    SPI_CS_POLARITY,
    SPI_CLK_POLARITY,
    SPI_CLK_PHASE,
    SPI_LSB_FIRST,
    SPI_HALF_DUPLEX,
) = (1 << i for i in range(8))


def SPI_DIV_WRITE(i):
    return i << 16


def SPI_DIV_READ(i):
    return i << 24


def SPI_CS(i):
    return i << 0


def SPI_WRITE_LENGTH(i):
    return i << 16


def SPI_READ_LENGTH(i):
    return i << 24


def _test_xfer(bus, cs, wlen, rlen, wdata):
    yield from bus.write(SPI_XFER_ADDR, SPI_CS(cs) |
                         SPI_WRITE_LENGTH(wlen) | SPI_READ_LENGTH(rlen))
    yield from bus.write(SPI_DATA_ADDR, wdata)
    yield


def _test_read(bus, sync=SPI_ACTIVE | SPI_PENDING):
    while (yield from bus.read(SPI_CONFIG_ADDR)) & sync:
        pass
    return (yield from bus.read(SPI_DATA_ADDR))


def _test_gen(bus):
    yield from bus.write(SPI_CONFIG_ADDR,
                         0*SPI_CLK_PHASE | 0*SPI_LSB_FIRST |
                         1*SPI_HALF_DUPLEX |
                         SPI_DIV_WRITE(3) | SPI_DIV_READ(5))
    yield from _test_xfer(bus, 0b01, 4, 0, 0x90000000)
    print(hex((yield from _test_read(bus))))
    yield from _test_xfer(bus, 0b10, 0, 4, 0x90000000)
    print(hex((yield from _test_read(bus))))
    yield from _test_xfer(bus, 0b11, 4, 4, 0x81000000)
    print(hex((yield from _test_read(bus))))
    yield from _test_xfer(bus, 0b01, 8, 32, 0x87654321)
    yield from _test_xfer(bus, 0b01, 0, 32, 0x12345678)
    print(hex((yield from _test_read(bus, SPI_PENDING))))
    print(hex((yield from _test_read(bus, SPI_ACTIVE))))
    return
    for cpol, cpha, lsb, clk in product(
            (0, 1), (0, 1), (0, 1), (0, 1)):
        yield from bus.write(SPI_CONFIG_ADDR,
                             cpol*SPI_CLK_POLARITY | cpha*SPI_CLK_PHASE |
                             lsb*SPI_LSB_FIRST | SPI_DIV_WRITE(clk) |
                             SPI_DIV_READ(clk))
        for wlen, rlen, wdata in product((0, 8, 32), (0, 8, 32),
                                         (0, 0xffffffff, 0xdeadbeef)):
            rdata = (yield from _test_xfer(bus, 0b1, wlen, rlen, wdata, True))
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
        self.cs_n = Signal(2)
        self.clk = Signal()
        self.mosi = Signal()
        self.miso = Signal()


class _TestTristate(Module):
    def __init__(self, t):
        oe = Signal()
        self.comb += [
            t.target.eq(t.o),
            oe.eq(t.oe),
            t.i.eq(t.o),
        ]

if __name__ == "__main__":
    from migen.fhdl.specials import Tristate

    pads = _TestPads()
    dut = SPIMaster(pads)
    dut.comb += pads.miso.eq(pads.mosi)
    # from migen.fhdl.verilog import convert
    # print(convert(dut))

    Tristate.lower = _TestTristate
    run_simulation(dut, _test_gen(dut.bus), vcd_name="spi_master.vcd")
