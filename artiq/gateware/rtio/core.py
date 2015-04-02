from fractions import Fraction

from migen.fhdl.std import *
from migen.bank.description import *
from migen.genlib.record import Record
from migen.genlib.cdc import *
from migen.genlib.fifo import AsyncFIFO
from migen.genlib.resetsync import AsyncResetSynchronizer

from artiq.gateware.rtio.rbus import get_fine_ts_width


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
#    * FIFO buffer latency: Tio
# Therefore we must choose:
#    guard_io_cycles > (4*Tio + 4*Tsys)/Tio
#
# We are writing to the FIFO from the buffer when the guard time has been
# reached. This can fill the FIFO and deassert the writable flag. A race
# condition occurs that causes problems if the deassertion happens between
# the CPU checking the writable flag (and reading 1) and writing a new event.
#
# When the FIFO is about to be full, it contains fifo_depth-1 events of
# strictly increasing timestamps.
#
# Thus the FIFO-filling event's timestamp must satisfy:
#    timestamp*Tio > (fifo_depth-1)*Tio + time
# We also have (guard time reached):
#    timestamp*Tio < time + guard_io_cycles*Tio
# [NB: time > counter.o_value_sys*Tio]
# Thus we must have:
#    guard_io_cycles > fifo_depth-1
#
# We can prevent overflows by choosing instead:
#    guard_io_cycles < fifo_depth-1

class _RTIOBankO(Module):
    def __init__(self, rbus, counter, fine_ts_width, fifo_depth, guard_io_cycles):
        self.sel = Signal(max=len(rbus))
        # timestamp and value must be valid 1 cycle before we
        self.timestamp = Signal(counter.width + fine_ts_width)
        self.value = Signal(2)
        self.writable = Signal()
        self.we = Signal()  # maximum throughput 1/2
        self.underflow = Signal()  # valid 2 cycles after we
        self.underflow_reset = Signal()
        self.sequence_error = Signal()
        self.sequence_error_reset = Signal()

        # # #

        signal_underflow = Signal()
        signal_sequence_error = Signal()
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
            buf_pending = Signal()
            buf = Record(ev_layout)
            buf_just_written = Signal()

            # Special cases
            replace = Signal()
            sequence_error = Signal()
            nop = Signal()
            self.sync.rsys += [
                replace.eq(self.timestamp == buf.timestamp[fine_ts_width:]),
                sequence_error.eq(self.timestamp < buf.timestamp[fine_ts_width:]),
                nop.eq(self.value == buf.value)
            ]
            self.comb += If(self.we & (self.sel == n) & sequence_error,
                signal_sequence_error.eq(1))

            # Buffer read and FIFO write
            self.comb += fifo.din.eq(buf)
            in_guard_time = Signal()
            self.comb += in_guard_time.eq(
                buf.timestamp[fine_ts_width:] < counter.o_value_sys + guard_io_cycles)
            self.sync.rsys += If(in_guard_time, buf_pending.eq(0))
            self.comb += \
                If(buf_pending,
                    If(in_guard_time,
                        If(buf_just_written,
                            signal_underflow.eq(1)
                        ).Else(
                            fifo.we.eq(1)
                        )
                    ),
                    If((self.we & (self.sel == n)
                            & ~replace & ~nop & ~sequence_error),
                       fifo.we.eq(1)
                    )
                )

            # Buffer write
            # Must come after read to handle concurrent read+write properly
            self.sync.rsys += [
                buf_just_written.eq(0),
                If(self.we & (self.sel == n) & ~nop & ~sequence_error,
                    buf_just_written.eq(1),
                    buf_pending.eq(1),
                    buf.timestamp.eq(self.timestamp),
                    buf.value.eq(self.value)
                )
            ]

            # Buffer output of FIFO to improve timing
            dout_stb = Signal()
            dout_ack = Signal()
            dout = Record(ev_layout)
            self.sync.rio += \
                If(fifo.re,
                    dout_stb.eq(1),
                    dout.eq(fifo.dout)
                ).Elif(dout_ack,
                    dout_stb.eq(0)
                )
            self.comb += fifo.re.eq(fifo.readable & (~dout_stb | dout_ack))

            # FIFO read through buffer
            self.comb += [
                dout_ack.eq(
                    dout.timestamp[fine_ts_width:] == counter.o_value_rio),
                chif.o_stb.eq(dout_stb & dout_ack),
                chif.o_value.eq(dout.value)
            ]
            if fine_ts_width:
                self.comb += chif.o_fine_ts.eq(
                    dout.timestamp[:fine_ts_width])

        self.comb += \
            self.writable.eq(Array(fifo.writable for fifo in fifos)[self.sel])
        self.sync.rsys += [
            If(self.underflow_reset, self.underflow.eq(0)),
            If(self.sequence_error_reset, self.sequence_error.eq(0)),
            If(signal_underflow, self.underflow.eq(1)),
            If(signal_sequence_error, self.sequence_error.eq(1))
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
    def __init__(self, phy, clk_freq, counter_width=63,
                 ofifo_depth=64, ififo_depth=64,
                 guard_io_cycles=20):
        fine_ts_width = get_fine_ts_width(phy.rbus)

        # Submodules
        self.submodules.counter = _RTIOCounter(
            counter_width, phy.loopback_latency)
        self.submodules.bank_o = _RTIOBankO(
            phy.rbus, self.counter, fine_ts_width, ofifo_depth, guard_io_cycles)
        self.submodules.bank_i = _RTIOBankI(
            phy.rbus, self.counter, fine_ts_width, ififo_depth)

        # CSRs
        self._reset = CSRStorage(reset=1)
        self._chan_sel = CSRStorage(flen(self.bank_o.sel))

        self._oe = CSR()

        self._o_timestamp = CSRStorage(counter_width + fine_ts_width)
        self._o_value = CSRStorage(2)
        self._o_we = CSR()
        self._o_status = CSRStatus(3)
        self._o_underflow_reset = CSR()
        self._o_sequence_error_reset = CSR()

        self._i_timestamp = CSRStatus(counter_width + fine_ts_width)
        self._i_value = CSRStatus()
        self._i_re = CSR()
        self._i_status = CSRStatus(2)
        self._i_overflow_reset = CSR()
        self._i_pileup_count = CSRStatus(16)
        self._i_pileup_reset = CSR()

        self._counter = CSRStatus(counter_width + fine_ts_width)
        self._counter_update = CSR()

        self._frequency_i = CSRStatus(32)
        self._frequency_fn = CSRStatus(8)
        self._frequency_fd = CSRStatus(8)


        # Clocking/Reset
        # Create rsys and rio domains based on sys and rio
        # with reset controlled by CSR.
        self.clock_domains.cd_rsys = ClockDomain()
        self.clock_domains.cd_rio = ClockDomain()
        self.comb += [
            self.cd_rsys.clk.eq(ClockSignal()),
            self.cd_rsys.rst.eq(self._reset.storage)
        ]
        self.comb += self.cd_rio.clk.eq(ClockSignal("rtio"))
        self.specials += AsyncResetSynchronizer(
            self.cd_rio, self._reset.storage)

        # OE
        oes = []
        for n, chif in enumerate(phy.rbus):
            if hasattr(chif, "oe"):
                self.sync += \
                    If(self._oe.re & (self._chan_sel.storage == n),
                        chif.oe.eq(self._oe.r)
                    )
                oes.append(chif.oe)
            else:
                oes.append(1)
        self.comb += self._oe.w.eq(Array(oes)[self._chan_sel.storage])

        # Output/Gate
        self.comb += [
            self.bank_o.sel.eq(self._chan_sel.storage),
            self.bank_o.timestamp.eq(self._o_timestamp.storage),
            self.bank_o.value.eq(self._o_value.storage),
            self.bank_o.we.eq(self._o_we.re),
            self._o_status.status.eq(Cat(~self.bank_o.writable,
                                           self.bank_o.underflow,
                                           self.bank_o.sequence_error)),
            self.bank_o.underflow_reset.eq(self._o_underflow_reset.re),
            self.bank_o.sequence_error_reset.eq(self._o_sequence_error_reset.re)
        ]

        # Input
        self.comb += [
            self.bank_i.sel.eq(self._chan_sel.storage),
            self._i_timestamp.status.eq(self.bank_i.timestamp),
            self._i_value.status.eq(self.bank_i.value),
            self.bank_i.re.eq(self._i_re.re),
            self._i_status.status.eq(Cat(~self.bank_i.readable, self.bank_i.overflow)),
            self.bank_i.overflow_reset.eq(self._i_overflow_reset.re),
            self._i_pileup_count.status.eq(self.bank_i.pileup_count),
            self.bank_i.pileup_reset.eq(self._i_pileup_reset.re)
        ]

        # Counter access
        self.sync += \
           If(self._counter_update.re,
               self._counter.status.eq(Cat(Replicate(0, fine_ts_width),
                                             self.counter.o_value_sys))
           )

        # Frequency
        clk_freq = Fraction(clk_freq).limit_denominator(255)
        clk_freq_i = int(clk_freq)
        clk_freq_f = clk_freq - clk_freq_i
        self.comb += [
            self._frequency_i.status.eq(clk_freq_i),
            self._frequency_fn.status.eq(clk_freq_f.numerator),
            self._frequency_fd.status.eq(clk_freq_f.denominator)
        ]
