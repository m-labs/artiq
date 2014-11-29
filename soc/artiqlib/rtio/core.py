from fractions import Fraction

from migen.fhdl.std import *
from migen.bank.description import *
from migen.genlib.record import Record
from migen.genlib.cdc import *
from migen.genlib.fifo import AsyncFIFO
from migen.genlib.resetsync import AsyncResetSynchronizer

from artiqlib.rtio.rbus import get_fine_ts_width


class _GrayCodeTransfer(Module):
    def __init__(self, width):
        self.i = Signal(width)  # in rio domain
        self.o = Signal(width)  # in rsys domain

        # # #

        # convert to Gray code
        value_gray_rio = Signal(width)
        self.sync.rio += value_gray_rio.eq(self.i ^ self.i[1:])
        # transfer to system clock domain
        value_gray_sys = Signal(width)
        self.specials += [
            NoRetiming(value_gray_rio),
            MultiReg(value_gray_rio, value_gray_sys, "rsys")
        ]
        # convert back to binary
        value_sys = Signal(width)
        self.comb += value_sys[-1].eq(value_gray_sys[-1])
        for i in reversed(range(width-1)):
            self.comb += value_sys[i].eq(value_sys[i+1] ^ value_gray_sys[i])
        self.sync.rsys += self.o.eq(value_sys)


class _RTIOCounter(Module):
    def __init__(self, width, loopback_latency):
        self.width = width
        # Timestamp counter in RTIO domain for outputs
        self.o_value_rio = Signal(width)
        # Timestamp counter resynchronized to sys domain
        # Lags behind o_value_rio, monotonic and glitch-free
        self.o_value_sys = Signal(width)
        # Timestamp counter in RTIO domain for inputs,
        # compensated for PHY loopback latency
        self.i_value_rio = Signal(width, reset=2**width-loopback_latency)

        # # #

        self.sync.rio += [
            self.o_value_rio.eq(self.o_value_rio + 1),
            self.i_value_rio.eq(self.i_value_rio + 1)
        ]
        gt = _GrayCodeTransfer(width)
        self.submodules += gt
        self.comb += gt.i.eq(self.o_value_rio), self.o_value_sys.eq(gt.o)


# CHOOSING A GUARD TIME
#
# The buffer must be transferred to the FIFO soon enough to account for:
#    * transfer of counter to sys domain: Tio + 2*Tsys + Tsys
#    * FIFO latency: Tsys + 2*Tio
# Therefore we must choose:
#    guard_io_cycles > (3*Tio + 4*Tsys)/Tio
#
# We are writing to the FIFO from the buffer when the guard time has been 
# reached without checking the FIFO's writable status. If the FIFO is full,
# this will produce an overflow and the event will be incorrectly discarded.
#
# When the FIFO is full, it contains fifo_depth events of strictly increasing
# timestamps.
#
# Thus the overflow-causing event's timestamp must satisfy:
#    timestamp*Tio > fifo_depth*Tio + time
# We also have (guard time reached):
#    timestamp*Tio < time + guard_io_cycles*Tio
# [NB: time > counter.o_value_sys*Tio]
# Thus we must have:
#    guard_io_cycles > fifo_depth
#
# We can prevent overflows by choosing instead:
#    guard_io_cycles < fifo_depth

class _RTIOBankO(Module):
    def __init__(self, rbus, counter, fine_ts_width, fifo_depth, guard_io_cycles):
        self.sel = Signal(max=len(rbus))
        self.timestamp = Signal(counter.width + fine_ts_width)
        self.value = Signal(2)
        self.writable = Signal()
        self.we = Signal()  # maximum throughput 1/2
        self.replace = Signal()
        self.underflow = Signal()  # valid 2 cycles after we/replace
        self.underflow_reset = Signal()

        # # #

        signal_underflow = Signal()
        fifos = []
        ev_layout = [("timestamp", counter.width + fine_ts_width),
                     ("value", 2)]
        for n, chif in enumerate(rbus):
            # FIFO
            fifo = RenameClockDomains(AsyncFIFO(ev_layout, fifo_depth),
                                      {"write": "rsys", "read": "rio"})
            self.submodules += fifo
            fifos.append(fifo)

            # Buffer
            buf_valid = Signal()
            buf = Record(ev_layout)
            buf_just_written = Signal()

            # Buffer read and FIFO write
            self.comb += fifo.din.eq(buf)
            in_guard_time = Signal()
            self.comb += in_guard_time.eq(
                buf.timestamp[fine_ts_width:] < counter.o_value_sys + guard_io_cycles)
            self.sync.rsys += If(in_guard_time, buf_valid.eq(0))
            self.comb += \
                If(buf_valid,
                    If(in_guard_time,
                        If(buf_just_written,
                            signal_underflow.eq(1)
                        ).Else(
                            fifo.we.eq(1)
                        )
                    ),
                    If(self.we & (self.sel == n), fifo.we.eq(1))
                )

            # Buffer write
            # Must come after read to handle concurrent read+write properly
            self.sync.rsys += [
                buf_just_written.eq(0),
                If((self.we | self.replace) & (self.sel == n),
                    # Replace operations on empty buffers may happen
                    # on underflows, which will be correctly reported.
                    buf_just_written.eq(1),
                    buf_valid.eq(1),
                    buf.timestamp.eq(self.timestamp),
                    buf.value.eq(self.value)
                )
            ]

            # FIFO read
            self.comb += [
                chif.o_stb.eq(fifo.readable &
                    (fifo.dout.timestamp[fine_ts_width:] == counter.o_value_rio)),
                chif.o_value.eq(fifo.dout.value),
                fifo.re.eq(chif.o_stb)
            ]
            if fine_ts_width:
                self.comb += chif.o_fine_ts.eq(
                    fifo.dout.timestamp[:fine_ts_width])

        self.comb += \
            self.writable.eq(Array(fifo.writable for fifo in fifos)[self.sel])
        self.sync.rsys += [
            If(self.underflow_reset, self.underflow.eq(0)),
            If(signal_underflow, self.underflow.eq(1))
        ]


class _RTIOBankI(Module):
    def __init__(self, rbus, counter, fine_ts_width, fifo_depth):
        self.sel = Signal(max=len(rbus))
        self.timestamp = Signal(counter.width + fine_ts_width)
        self.value = Signal()
        self.readable = Signal()
        self.re = Signal()
        self.overflow = Signal()
        self.overflow_reset = Signal()
        self.pileup_count = Signal(16)
        self.pileup_reset = Signal()

        # # #

        timestamps = []
        values = []
        readables = []
        overflows = []
        pileup_counts = []
        ev_layout = [("timestamp", counter.width+fine_ts_width),
                     ("value", 1)]
        for n, chif in enumerate(rbus):
            if hasattr(chif, "oe"):
                sensitivity = Signal(2)
                self.sync.rio += If(~chif.oe & chif.o_stb,
                                    sensitivity.eq(chif.o_value))

                fifo = RenameClockDomains(AsyncFIFO(ev_layout, fifo_depth),
                                          {"read": "rsys", "write": "rio"})
                self.submodules += fifo

                # FIFO write
                if fine_ts_width:
                    full_ts = Cat(chif.i_fine_ts, counter.i_value_rio)
                else:
                    full_ts = counter.i_value_rio
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
                overflow_reset_sync = PulseSynchronizer("rsys", "rio")
                self.submodules += overflow_reset_sync
                self.comb += overflow_reset_sync.i.eq(
                    self.overflow_reset & (self.sel == n))
                self.sync.rio += [
                    If(overflow_reset_sync.o, overflow.eq(0)),
                    If(fifo.we & ~fifo.writable, overflow.eq(1))
                ]
                overflow_sys = Signal()
                self.specials += MultiReg(overflow, overflow_sys, "rsys")
                overflows.append(overflow_sys)

                pileup_count = Signal(16)
                pileup_count_reset_sync = PulseSynchronizer("rsys", "rio")
                self.submodules += pileup_count_reset_sync
                self.comb += pileup_count_reset_sync.i.eq(
                    self.pileup_reset & (self.sel == n))
                self.sync.rio += \
                    If(pileup_count_reset_sync.o,
                        pileup_count.eq(0)
                    ).Elif(chif.i_pileup,
                        If(pileup_count != 2**16 - 1,  # saturate
                            pileup_count.eq(pileup_count + 1)
                        )
                    )
                pileup_count_sync = _GrayCodeTransfer(16)
                self.submodules += pileup_count_sync
                self.comb += pileup_count_sync.i.eq(pileup_count)
                pileup_counts.append(pileup_count_sync.o)
            else:
                timestamps.append(0)
                values.append(0)
                readables.append(0)
                overflows.append(0)
                pileup_counts.append(0)

        self.comb += [
            self.timestamp.eq(Array(timestamps)[self.sel]),
            self.value.eq(Array(values)[self.sel]),
            self.readable.eq(Array(readables)[self.sel]),
            self.overflow.eq(Array(overflows)[self.sel]),
            self.pileup_count.eq(Array(pileup_counts)[self.sel])
        ]


class RTIO(Module, AutoCSR):
    def __init__(self, phy, clk_freq, counter_width=32,
                 ofifo_depth=64, ififo_depth=64,
                 guard_io_cycles=20):
        fine_ts_width = get_fine_ts_width(phy.rbus)

        # Submodules
        self.submodules.counter = _RTIOCounter(
            counter_width, phy.loopback_latency)
        self.submodules.bank_o = _RTIOBankO(
            phy.rbus, self.counter, fine_ts_width, ofifo_depth, guard_io_cycles)
        self.submodules.bank_i = _RTIOBankI(
            phy.rbus, self.counter, fine_ts_width, ofifo_depth)

        # CSRs
        self._r_reset = CSRStorage(reset=1)
        self._r_chan_sel = CSRStorage(flen(self.bank_o.sel))

        self._r_oe = CSR()

        self._r_o_timestamp = CSRStorage(counter_width + fine_ts_width)
        self._r_o_value = CSRStorage(2)
        self._r_o_writable = CSRStatus()
        self._r_o_we = CSR()
        self._r_o_replace = CSR()
        self._r_o_underflow = CSRStatus()
        self._r_o_underflow_reset = CSR()

        self._r_i_timestamp = CSRStatus(counter_width + fine_ts_width)
        self._r_i_value = CSRStatus()
        self._r_i_readable = CSRStatus()
        self._r_i_re = CSR()
        self._r_i_overflow = CSRStatus()
        self._r_i_overflow_reset = CSR()
        self._r_i_pileup_count = CSRStatus(16)
        self._r_i_pileup_reset = CSR()

        self._r_counter = CSRStatus(counter_width + fine_ts_width)
        self._r_counter_update = CSR()

        self._r_frequency_i = CSRStatus(32)
        self._r_frequency_fn = CSRStatus(8)
        self._r_frequency_fd = CSRStatus(8)


        # Clocking/Reset
        # Create rsys and rio domains based on sys and rio
        # with reset controlled by CSR.
        self.clock_domains.cd_rsys = ClockDomain()
        self.clock_domains.cd_rio = ClockDomain()
        self.comb += [
            self.cd_rsys.clk.eq(ClockSignal()),
            self.cd_rsys.rst.eq(self._r_reset.storage)
        ]
        self.comb += self.cd_rio.clk.eq(ClockSignal("rtio"))
        self.specials += AsyncResetSynchronizer(
            self.cd_rio, self._r_reset.storage)

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
            self.bank_o.sel.eq(self._r_chan_sel.storage),
            self.bank_o.timestamp.eq(self._r_o_timestamp.storage),
            self.bank_o.value.eq(self._r_o_value.storage),
            self._r_o_writable.status.eq(self.bank_o.writable),
            self.bank_o.we.eq(self._r_o_we.re),
            self.bank_o.replace.eq(self._r_o_replace.re),
            self._r_o_underflow.status.eq(self.bank_o.underflow),
            self.bank_o.underflow_reset.eq(self._r_o_underflow_reset.re)
        ]

        # Input
        self.comb += [
            self.bank_i.sel.eq(self._r_chan_sel.storage),
            self._r_i_timestamp.status.eq(self.bank_i.timestamp),
            self._r_i_value.status.eq(self.bank_i.value),
            self._r_i_readable.status.eq(self.bank_i.readable),
            self.bank_i.re.eq(self._r_i_re.re),
            self._r_i_overflow.status.eq(self.bank_i.overflow),
            self.bank_i.overflow_reset.eq(self._r_i_overflow_reset.re),
            self._r_i_pileup_count.status.eq(self.bank_i.pileup_count),
            self.bank_i.pileup_reset.eq(self._r_i_pileup_reset.re)
        ]

        # Counter access
        self.sync += \
           If(self._r_counter_update.re,
               self._r_counter.status.eq(Cat(Replicate(0, fine_ts_width),
                                             self.counter.o_value_sys))
           )

        # Frequency
        clk_freq = Fraction(clk_freq).limit_denominator(255)
        clk_freq_i = int(clk_freq)
        clk_freq_f = clk_freq - clk_freq_i
        self.comb += [
            self._r_frequency_i.status.eq(clk_freq_i),
            self._r_frequency_fn.status.eq(clk_freq_f.numerator),
            self._r_frequency_fd.status.eq(clk_freq_f.denominator)
        ]
