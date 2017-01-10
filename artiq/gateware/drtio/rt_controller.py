from migen import *
from migen.genlib.cdc import MultiReg
from migen.genlib.misc import WaitTimer
from migen.genlib.resetsync import AsyncResetSynchronizer

from misoc.interconnect.csr import *

from artiq.gateware.rtio.cdc import RTIOCounter
from artiq.gateware.rtio import cri


class _CSRs(AutoCSR):
    def __init__(self):
        self.chan_sel_override = CSRStorage(16)
        self.chan_sel_override_en = CSRStorage()

        self.tsc_correction = CSRStorage(64)
        self.set_time = CSR()
        self.underflow_margin = CSRStorage(16, reset=200)

        self.reset = CSR()
        self.reset_phy = CSR()

        self.o_get_fifo_space = CSR()
        self.o_dbg_fifo_space = CSRStatus(16)
        self.o_dbg_last_timestamp = CSRStatus(64)
        self.o_reset_channel_status = CSR()
        self.o_wait = CSRStatus()
        self.o_fifo_space_timeout = CSR()


class RTController(Module):
    def __init__(self, rt_packets, channel_count, fine_ts_width):
        self.csrs = _CSRs()
        self.cri = cri.Interface()
        self.comb += self.cri.arb_gnt.eq(1)

        # channel selection
        chan_sel = Signal(16)
        self.comb += chan_sel.eq(
            Mux(self.csrs.chan_sel_override_en.storage,
                self.csrs.chan_sel_override.storage,
                self.cri.chan_sel[:16]))

        # master RTIO counter and counter synchronization
        self.submodules.counter = RTIOCounter(64-fine_ts_width)
        self.comb += self.cri.counter.eq(self.counter.value_sys << fine_ts_width)
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

        # reset
        self.sync += [
            If(rt_packets.reset_ack, rt_packets.reset_stb.eq(0)),
            If(self.csrs.reset.re,
                rt_packets.reset_stb.eq(1),
                rt_packets.reset_phy.eq(0)
            ),
            If(self.csrs.reset_phy.re,
                rt_packets.reset_stb.eq(1),
                rt_packets.reset_phy.eq(1)
            ),
        ]

        local_reset = Signal(reset=1)
        self.sync += local_reset.eq(self.csrs.reset.re)
        local_reset.attr.add("no_retiming")
        self.clock_domains.cd_sys_with_rst = ClockDomain()
        self.clock_domains.cd_rtio_with_rst = ClockDomain()
        self.comb += [
            self.cd_sys_with_rst.clk.eq(ClockSignal()),
            self.cd_sys_with_rst.rst.eq(local_reset)
        ]
        self.comb += self.cd_rtio_with_rst.clk.eq(ClockSignal("rtio"))
        self.specials += AsyncResetSynchronizer(self.cd_rtio_with_rst, local_reset)

        # remote channel status cache
        fifo_spaces_mem = Memory(16, channel_count)
        fifo_spaces = fifo_spaces_mem.get_port(write_capable=True)
        self.specials += fifo_spaces_mem, fifo_spaces
        last_timestamps_mem = Memory(64, channel_count)
        last_timestamps = last_timestamps_mem.get_port(write_capable=True)
        self.specials += last_timestamps_mem, last_timestamps

        # common packet fields
        rt_packets_fifo_request = Signal()
        self.comb += [
            fifo_spaces.adr.eq(chan_sel),
            last_timestamps.adr.eq(chan_sel),
            last_timestamps.dat_w.eq(self.cri.o_timestamp),
            rt_packets.write_channel.eq(chan_sel),
            rt_packets.write_address.eq(self.cri.o_address),
            rt_packets.write_data.eq(self.cri.o_data),
            If(rt_packets_fifo_request,
                rt_packets.write_timestamp.eq(0xffff000000000000)
            ).Else(
                rt_packets.write_timestamp.eq(self.cri.o_timestamp)
            )
        ]

        fsm = ClockDomainsRenamer("sys_with_rst")(FSM())
        self.submodules += fsm

        status_wait = Signal()
        status_underflow = Signal()
        status_sequence_error = Signal()
        self.comb += [
            self.cri.o_status.eq(Cat(
                status_wait, status_underflow, status_sequence_error)),
            self.csrs.o_wait.status.eq(status_wait)
        ]
        sequence_error_set = Signal()
        underflow_set = Signal()
        self.sync.sys_with_rst += [
            If(self.cri.cmd == cri.commands["o_underflow_reset"], status_underflow.eq(0)),
            If(self.cri.cmd == cri.commands["o_sequence_error_reset"], status_sequence_error.eq(0)),
            If(underflow_set, status_underflow.eq(1)),
            If(sequence_error_set, status_sequence_error.eq(1))
        ]

        signal_fifo_space_timeout = Signal()
        self.sync.sys_with_rst += [
            If(self.csrs.o_fifo_space_timeout.re, self.csrs.o_fifo_space_timeout.w.eq(0)),
            If(signal_fifo_space_timeout, self.csrs.o_fifo_space_timeout.w.eq(1))
        ]
        timeout_counter = WaitTimer(8191)
        self.submodules += timeout_counter

        # TODO: collision, replace, busy
        cond_sequence_error = self.cri.o_timestamp < last_timestamps.dat_r
        cond_underflow = ((self.cri.o_timestamp[fine_ts_width:]
                           - self.csrs.underflow_margin.storage[fine_ts_width:]) < self.counter.value_sys)

        fsm.act("IDLE",
            If(self.cri.cmd == cri.commands["write"],
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
                fifo_spaces.dat_w.eq(fifo_spaces.dat_r - 1),
                last_timestamps.we.eq(1),
                If(fifo_spaces.dat_r <= 1,
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
            rt_packets.fifo_space_not_ack.eq(1),
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
                If(rt_packets.fifo_space != 0,
                    NextState("IDLE")
                ).Else(
                    NextState("GET_FIFO_SPACE")
                )
            ),
            timeout_counter.wait.eq(1),
            If(timeout_counter.done,
                signal_fifo_space_timeout.eq(1),
                NextState("IDLE")
            )
        )

        # channel state access
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

    def get_csrs(self):
        return self.csrs.get_csrs()


class RTManager(Module, AutoCSR):
    def __init__(self, rt_packets):
        self.request_echo = CSR()

        self.packet_err_present = CSR()
        self.packet_err_code = CSRStatus(8)

        self.update_packet_cnt = CSR()
        self.packet_cnt_tx = CSRStatus(32)
        self.packet_cnt_rx = CSRStatus(32)

        # # #

        self.comb += self.request_echo.w.eq(rt_packets.echo_stb)
        self.sync += [
            If(rt_packets.echo_ack, rt_packets.echo_stb.eq(0)),
            If(self.request_echo.re, rt_packets.echo_stb.eq(1))
        ]

        self.comb += [
            self.packet_err_present.w.eq(rt_packets.error_not),
            rt_packets.error_not_ack.eq(self.packet_err_present.re),
            self.packet_err_code.status.eq(rt_packets.error_code)
        ]

        self.sync += \
            If(self.update_packet_cnt.re,
                self.packet_cnt_tx.status.eq(rt_packets.packet_cnt_tx),
                self.packet_cnt_rx.status.eq(rt_packets.packet_cnt_rx)
            )
