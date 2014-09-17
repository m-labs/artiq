from migen.fhdl.std import *
from migen.bank.description import *
from migen.genlib.fifo import SyncFIFO

from artiqlib.rtio.rbus import get_fine_ts_width


class _RTIOBankO(Module):
    def __init__(self, rbus, counter_width, fine_ts_width,
                 fifo_depth, counter_init):
        self.sel = Signal(max=len(rbus))
        self.timestamp = Signal(counter_width+fine_ts_width)
        self.value = Signal(2)
        self.writable = Signal()
        self.we = Signal()
        self.replace = Signal()
        self.underflow = Signal()
        self.level = Signal(bits_for(fifo_depth))
        self.counter = Signal(counter_width, reset=counter_init)

        # # #

        self.sync += self.counter.eq(self.counter + 1)

        # detect underflows
        self.sync += \
            If((self.we & self.writable) | self.replace,
                If(self.timestamp[fine_ts_width:] < self.counter + 2,
                    self.underflow.eq(1))
            )

        fifos = []
        for n, chif in enumerate(rbus):
            fifo = SyncFIFO([
                ("timestamp", counter_width+fine_ts_width), ("value", 2)],
                2 if chif.mini else fifo_depth)
            self.submodules += fifo
            fifos.append(fifo)

            # FIFO replace/write
            self.comb += [
                fifo.din.timestamp.eq(self.timestamp),
                fifo.din.value.eq(self.value),
                fifo.we.eq((self.we | self.replace) & (self.sel == n)),
                fifo.replace.eq(self.replace)
            ]

            # FIFO read
            self.comb += [
                chif.o_stb.eq(fifo.readable &
                    (fifo.dout.timestamp[fine_ts_width:] == self.counter)),
                chif.o_value.eq(fifo.dout.value),
                fifo.re.eq(chif.o_stb)
            ]
            if fine_ts_width:
                self.comb += chif.o_fine_ts.eq(
                    fifo.dout.timestamp[:fine_ts_width])

        selfifo = Array(fifos)[self.sel]
        self.comb += [
            self.writable.eq(selfifo.writable),
            self.level.eq(selfifo.level)
        ]


class _RTIOBankI(Module):
    def __init__(self, rbus, counter_width, fine_ts_width, fifo_depth):
        self.sel = Signal(max=len(rbus))
        self.timestamp = Signal(counter_width+fine_ts_width)
        self.value = Signal()
        self.readable = Signal()
        self.re = Signal()
        self.overflow = Signal()
        self.pileup = Signal()

        ###

        counter = Signal(counter_width)
        self.sync += counter.eq(counter + 1)

        timestamps = []
        values = []
        readables = []
        overflows = []
        pileups = []
        for n, chif in enumerate(rbus):
            if hasattr(chif, "oe"):
                sensitivity = Signal(2)
                self.sync += If(~chif.oe & chif.o_stb,
                    sensitivity.eq(chif.o_value))

                fifo = SyncFIFO([
                    ("timestamp", counter_width+fine_ts_width), ("value", 1)],
                    fifo_depth)
                self.submodules += fifo

                # FIFO write
                if fine_ts_width:
                    full_ts = Cat(chif.i_fine_ts, counter)
                else:
                    full_ts = counter
                self.comb += [
                    fifo.din.timestamp.eq(full_ts),
                    fifo.din.value.eq(chif.i_value),
                    fifo.we.eq(
                        ~chif.oe & chif.i_stb &
                        ((chif.i_value & sensitivity[0])
                            | (~chif.i_value & sensitivity[1])))
                ]

                # FIFO read
                timestamps.append(fifo.dout.timestamp)
                values.append(fifo.dout.value)
                readables.append(fifo.readable)
                self.comb += fifo.re.eq(self.re & (self.sel == n))

                overflow = Signal()
                self.sync += If(fifo.we & ~fifo.writable, overflow.eq(1))
                overflows.append(overflow)

                pileup = Signal()
                self.sync += If(chif.i_pileup, pileup.eq(1))
                pileups.append(pileup)
            else:
                timestamps.append(0)
                values.append(0)
                readables.append(0)
                overflows.append(0)
                pileups.append(0)

        self.comb += [
            self.timestamp.eq(Array(timestamps)[self.sel]),
            self.value.eq(Array(values)[self.sel]),
            self.readable.eq(Array(readables)[self.sel]),
            self.overflow.eq(Array(overflows)[self.sel]),
            self.pileup.eq(Array(pileups)[self.sel])
        ]


class RTIO(Module, AutoCSR):
    def __init__(self, phy, counter_width=32, ofifo_depth=8, ififo_depth=8):
        fine_ts_width = get_fine_ts_width(phy.rbus)

        # Submodules
        self.submodules.bank_o = InsertReset(_RTIOBankO(
            phy.rbus,
            counter_width, fine_ts_width, ofifo_depth,
            phy.loopback_latency))
        self.submodules.bank_i = InsertReset(_RTIOBankI(
            phy.rbus,
            counter_width, fine_ts_width, ofifo_depth))

        # CSRs
        self._r_reset = CSRStorage(reset=1)
        self._r_chan_sel = CSRStorage(flen(self.bank_o.sel))

        self._r_oe = CSR()

        self._r_o_timestamp = CSRStorage(counter_width+fine_ts_width)
        self._r_o_value = CSRStorage(2)
        self._r_o_writable = CSRStatus()
        self._r_o_we = CSR()
        self._r_o_replace = CSR()
        self._r_o_error = CSRStatus(2)
        self._r_o_level = CSRStatus(bits_for(ofifo_depth))

        self._r_i_timestamp = CSRStatus(counter_width+fine_ts_width)
        self._r_i_value = CSRStatus()
        self._r_i_readable = CSRStatus()
        self._r_i_re = CSR()
        self._r_i_error = CSRStatus(2)

        self._r_counter = CSRStatus(counter_width+fine_ts_width)
        self._r_counter_update = CSR()

        # Counter
        self.sync += \
           If(self._r_counter_update.re,
               self._r_counter.status.eq(Cat(Replicate(0, fine_ts_width),
                                             self.bank_o.counter))
           )

        # OE
        oes = []
        for n, chif in enumerate(phy.rbus):
            if hasattr(chif, "oe"):
                self.sync += \
                    If(self._r_oe.re & (self._r_chan_sel.storage == n),
                        chif.oe.eq(self._r_oe.r)
                    )
                oes.append(chif.oe)
            else:
                oes.append(1)
        self.comb += self._r_oe.w.eq(Array(oes)[self._r_chan_sel.storage])

        # Output/Gate
        self.comb += [
            self.bank_o.reset.eq(self._r_reset.storage),
            self.bank_o.sel.eq(self._r_chan_sel.storage),
            self.bank_o.timestamp.eq(self._r_o_timestamp.storage),
            self.bank_o.value.eq(self._r_o_value.storage),
            self._r_o_writable.status.eq(self.bank_o.writable),
            self.bank_o.we.eq(self._r_o_we.re),
            self.bank_o.replace.eq(self._r_o_replace.re),
            self._r_o_error.status.eq(self.bank_o.underflow),
            self._r_o_level.status.eq(self.bank_o.level)
        ]

        # Input
        self.comb += [
            self.bank_i.reset.eq(self._r_reset.storage),
            self.bank_i.sel.eq(self._r_chan_sel.storage),
            self._r_i_timestamp.status.eq(self.bank_i.timestamp),
            self._r_i_value.status.eq(self.bank_i.value),
            self._r_i_readable.status.eq(self.bank_i.readable),
            self.bank_i.re.eq(self._r_i_re.re),
            self._r_i_error.status.eq(
                Cat(self.bank_i.overflow, self.bank_i.pileup))
        ]
