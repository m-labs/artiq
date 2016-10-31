from migen import *
from migen.genlib.cdc import MultiReg

from misoc.interconnect.csr import *

from artiq.gateware.rtio.cdc import RTIOCounter
from artiq.gateware.rtio.kernel_csrs import KernelCSRs


class _CSRs(AutoCSR):
    def __init__(self):
        self.chan_sel_override = CSRStorage(16)
        self.chan_sel_override_en = CSRStorage()

        self.tsc_correction = CSRStorage(64)
        self.set_time = CSR()
        self.underflow_margin = CSRStorage(16, reset=200)

        self.o_get_fifo_space = CSR()
        self.o_dbg_fifo_space = CSRStatus(16)
        self.o_dbg_last_timestamp = CSRStatus(64)
        self.o_reset_channel_status = CSR()
        self.o_wait = CSRStatus()

        self.err_present = CSR()
        self.err_code = CSRStatus(8)


class RTController(Module):
    def __init__(self, rt_packets, channel_count, fine_ts_width):
        self.kcsrs = KernelCSRs()
        self.csrs = _CSRs()

        chan_sel = Signal(16)
        self.comb += chan_sel.eq(
            Mux(self.csrs.chan_sel_override_en.storage,
                self.csrs.chan_sel_override.storage,
                self.kcsrs.chan_sel.storage))

        self.submodules.counter = RTIOCounter(64-fine_ts_width)
        self.sync += If(self.kcsrs.counter_update.re, 
                        self.kcsrs.counter.status.eq(self.counter.value_sys))
        tsc_correction = Signal(64)
        self.csrs.tsc_correction.storage.attr.add("no_retiming")
        self.specials += MultiReg(self.csrs.tsc_correction.storage, tsc_correction)
        self.comb += [ 
            rt_packets.tsc_value.eq(
                self.counter.value_rtio + tsc_correction),
            self.csrs.set_time.w.eq(rt_packets.set_time_stb)
        ]
        self.sync += [
            If(rt_packets.set_time_ack, rt_packets.set_time_stb.eq(0)),
            If(self.csrs.set_time.re, rt_packets.set_time_stb.eq(1))
        ]

        fifo_spaces_mem = Memory(16, channel_count)
        fifo_spaces = fifo_spaces_mem.get_port(write_capable=True)
        self.specials += fifo_spaces_mem, fifo_spaces
        last_timestamps_mem = Memory(64, channel_count)
        last_timestamps = last_timestamps_mem.get_port(write_capable=True)
        self.specials += last_timestamps_mem, last_timestamps

        rt_packets_fifo_request = Signal()
        self.comb += [
            fifo_spaces.adr.eq(chan_sel),
            last_timestamps.adr.eq(chan_sel),
            last_timestamps.dat_w.eq(self.kcsrs.o_timestamp.storage),
            rt_packets.write_channel.eq(chan_sel),
            rt_packets.write_address.eq(self.kcsrs.o_address.storage),
            rt_packets.write_data.eq(self.kcsrs.o_data.storage),
            If(rt_packets_fifo_request,
                rt_packets.write_timestamp.eq(0xffff000000000000)
            ).Else(
                rt_packets.write_timestamp.eq(self.kcsrs.o_timestamp.storage)
            )
        ]

        fsm = FSM()
        self.submodules += fsm

        status_wait = Signal()
        status_underflow = Signal()
        status_sequence_error = Signal()
        self.comb += [
            self.kcsrs.o_status.status.eq(Cat(
                status_wait, status_underflow, status_sequence_error)),
            self.csrs.o_wait.status.eq(status_wait)
        ]
        sequence_error_set = Signal()
        underflow_set = Signal()
        self.sync += [
            If(self.kcsrs.o_underflow_reset.re, status_underflow.eq(0)),
            If(self.kcsrs.o_sequence_error_reset.re, status_sequence_error.eq(0)),
            If(underflow_set, status_underflow.eq(1)),
            If(sequence_error_set, status_sequence_error.eq(1)),
        ]

        # TODO: collision, replace, busy
        cond_sequence_error = self.kcsrs.o_timestamp.storage < last_timestamps.dat_r
        cond_underflow = ((self.kcsrs.o_timestamp.storage[fine_ts_width:]
                           - self.csrs.underflow_margin.storage[fine_ts_width:]) < self.counter.value_sys)
        cond_fifo_emptied = ((last_timestamps.dat_r[fine_ts_width:] < self.counter.value_sys)
                             & (last_timestamps.dat_r != 0))

        fsm.act("IDLE",
            If(self.kcsrs.o_we.re,
                If(cond_sequence_error,
                    sequence_error_set.eq(1)
                ).Elif(cond_underflow,
                    underflow_set.eq(1)
                ).Else(
                    NextState("WRITE")
                )
            ),
            If(self.csrs.o_get_fifo_space.re,
                NextState("GET_FIFO_SPACE")
            )
        )
        fsm.act("WRITE",
            status_wait.eq(1),
            rt_packets.write_stb.eq(1),
            If(rt_packets.write_ack,
                fifo_spaces.we.eq(1),
                If(cond_fifo_emptied,
                    fifo_spaces.dat_w.eq(1),
                ).Else(
                    fifo_spaces.dat_w.eq(fifo_spaces.dat_r - 1)
                ),
                last_timestamps.we.eq(1),
                If(~cond_fifo_emptied & (fifo_spaces.dat_r <= 1),
                    NextState("GET_FIFO_SPACE")
                ).Else(
                    NextState("IDLE")
                )
            )
        )
        fsm.act("GET_FIFO_SPACE",
            status_wait.eq(1),
            rt_packets_fifo_request.eq(1),
            rt_packets.write_stb.eq(1),
            If(rt_packets.write_ack,
                NextState("GET_FIFO_SPACE_REPLY")
            )
        )
        fsm.act("GET_FIFO_SPACE_REPLY",
            status_wait.eq(1),
            fifo_spaces.dat_w.eq(rt_packets.fifo_space),
            fifo_spaces.we.eq(1),
            rt_packets.fifo_space_not_ack.eq(1),
            If(rt_packets.fifo_space_not,
                If(rt_packets.fifo_space > 0,
                    NextState("IDLE")
                ).Else(
                    NextState("GET_FIFO_SPACE")
                )
            )
        )

        self.comb += [
            self.csrs.o_dbg_fifo_space.status.eq(fifo_spaces.dat_r),
            self.csrs.o_dbg_last_timestamp.status.eq(last_timestamps.dat_r),
            If(self.csrs.o_reset_channel_status.re,
                fifo_spaces.dat_w.eq(0),
                fifo_spaces.we.eq(1),
                last_timestamps.dat_w.eq(0),
                last_timestamps.we.eq(1)
            )
        ]

        self.comb += [
            self.csrs.err_present.w.eq(rt_packets.error_not),
            rt_packets.error_not_ack.eq(self.csrs.err_present.re),
            self.csrs.err_code.status.eq(rt_packets.error_code)
        ]

    def get_kernel_csrs(self):
        return self.kcsrs.get_csrs()

    def get_csrs(self):
        return self.csrs.get_csrs()
