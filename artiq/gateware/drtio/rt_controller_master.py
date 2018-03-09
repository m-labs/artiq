"""Real-time controller for master"""

from migen import *
from migen.genlib.cdc import MultiReg
from migen.genlib.misc import WaitTimer
from migen.genlib.resetsync import AsyncResetSynchronizer

from misoc.interconnect.csr import *

from artiq.gateware.rtio.cdc import GrayCodeTransfer
from artiq.gateware.rtio import cri


class _CSRs(AutoCSR):
    def __init__(self):
        self.link_up = CSRStorage()

        self.protocol_error = CSR(3)

        self.set_time = CSR()
        self.underflow_margin = CSRStorage(16, reset=300)

        self.o_get_buffer_space = CSR()
        self.o_dbg_buffer_space = CSRStatus(16)
        self.o_dbg_buffer_space_req_cnt = CSRStatus(32)
        self.o_wait = CSRStatus()


class RTIOCounter(Module):
    def __init__(self, width):
        self.width = width
        # Timestamp counter in RTIO domain
        self.value_rtio = Signal(width)
        # Timestamp counter resynchronized to sys domain
        # Lags behind value_rtio, monotonic and glitch-free
        self.value_sys = Signal(width)

        # # #

        # note: counter is in rtio domain and never affected by the reset CSRs
        self.sync.rtio += self.value_rtio.eq(self.value_rtio + 1)
        gt = GrayCodeTransfer(width)
        self.submodules += gt
        self.comb += gt.i.eq(self.value_rtio), self.value_sys.eq(gt.o)


class RTController(Module):
    def __init__(self, rt_packet, channel_count, fine_ts_width):
        self.csrs = _CSRs()
        self.cri = cri.Interface()

        # reset
        local_reset = Signal(reset=1)
        self.sync += local_reset.eq(~self.csrs.link_up.storage)
        local_reset.attr.add("no_retiming")
        self.clock_domains.cd_sys_with_rst = ClockDomain()
        self.clock_domains.cd_rtio_with_rst = ClockDomain()
        self.comb += [
            self.cd_sys_with_rst.clk.eq(ClockSignal()),
            self.cd_sys_with_rst.rst.eq(local_reset)
        ]
        self.comb += self.cd_rtio_with_rst.clk.eq(ClockSignal("rtio"))
        self.specials += AsyncResetSynchronizer(self.cd_rtio_with_rst, local_reset)

        # protocol errors
        err_unknown_packet_type = Signal()
        err_packet_truncated = Signal()
        signal_buffer_space_timeout = Signal()
        err_buffer_space_timeout = Signal()
        self.sync.sys_with_rst += [
            If(self.csrs.protocol_error.re,
                If(self.csrs.protocol_error.r[0], err_unknown_packet_type.eq(0)),
                If(self.csrs.protocol_error.r[1], err_packet_truncated.eq(0)),
                If(self.csrs.protocol_error.r[2], err_buffer_space_timeout.eq(0))
            ),
            If(rt_packet.err_unknown_packet_type, err_unknown_packet_type.eq(1)),
            If(rt_packet.err_packet_truncated, err_packet_truncated.eq(1)),
            If(signal_buffer_space_timeout, err_buffer_space_timeout.eq(1))
        ]
        self.comb += self.csrs.protocol_error.w.eq(
            Cat(err_unknown_packet_type, err_packet_truncated, err_buffer_space_timeout))

        # master RTIO counter and counter synchronization
        self.submodules.counter = RTIOCounter(64-fine_ts_width)
        self.comb += [
            self.cri.counter.eq(self.counter.value_sys << fine_ts_width),
            rt_packet.tsc_value.eq(self.counter.value_rtio),
            self.csrs.set_time.w.eq(rt_packet.set_time_stb)
        ]
        self.sync += [
            If(rt_packet.set_time_ack, rt_packet.set_time_stb.eq(0)),
            If(self.csrs.set_time.re, rt_packet.set_time_stb.eq(1))
        ]

        # common packet fields
        chan_sel = self.cri.chan_sel[:16]
        rt_packet_buffer_request = Signal()
        rt_packet_read_request = Signal()
        self.comb += [
            rt_packet.sr_channel.eq(chan_sel),
            rt_packet.sr_address.eq(self.cri.o_address),
            rt_packet.sr_data.eq(self.cri.o_data),
            rt_packet.sr_timestamp.eq(self.cri.timestamp),
            If(rt_packet_buffer_request,
                rt_packet.sr_notwrite.eq(1),
                rt_packet.sr_address.eq(0)
            ),
            If(rt_packet_read_request,
                rt_packet.sr_notwrite.eq(1),
                rt_packet.sr_address.eq(1)
            )
        ]

        # output status
        o_status_wait = Signal()
        o_status_underflow = Signal()
        self.comb += [
            self.cri.o_status.eq(Cat(
                o_status_wait, o_status_underflow, ~self.csrs.link_up.storage)),
            self.csrs.o_wait.status.eq(o_status_wait)
        ]
        o_underflow_set = Signal()
        self.sync.sys_with_rst += [
            If(self.cri.cmd == cri.commands["write"],
                o_status_underflow.eq(0)
            ),
            If(o_underflow_set, o_status_underflow.eq(1))
        ]

        timeout_counter = WaitTimer(8191)
        self.submodules += timeout_counter

        cond_underflow = Signal()
        self.comb += cond_underflow.eq((self.cri.timestamp[fine_ts_width:]
                           - self.csrs.underflow_margin.storage[fine_ts_width:]) < self.counter.value_sys)

        buffer_space = Signal(16)

        # input status
        i_status_wait_event = Signal()
        i_status_overflow = Signal()
        i_status_wait_status = Signal()
        self.comb += self.cri.i_status.eq(Cat(
            i_status_wait_event, i_status_overflow, i_status_wait_status,
            ~self.csrs.link_up.storage))

        load_read_reply = Signal()
        self.sync.sys_with_rst += [
            If(load_read_reply,
                i_status_wait_event.eq(0),
                i_status_overflow.eq(0),
                If(rt_packet.read_no_event,
                    If(rt_packet.read_is_overflow,
                        i_status_overflow.eq(1)
                    ).Else(
                        i_status_wait_event.eq(1)
                    )
                ),
                self.cri.i_data.eq(rt_packet.read_data),
                self.cri.i_timestamp.eq(rt_packet.read_timestamp)
            )
        ]

        # FSM
        fsm = ClockDomainsRenamer("sys_with_rst")(FSM())
        self.submodules += fsm

        fsm.act("IDLE",
            If(self.cri.cmd == cri.commands["write"],
                If(cond_underflow,
                    o_underflow_set.eq(1)
                ).Else(
                    NextState("WRITE")
                )
            ),
            If(self.cri.cmd == cri.commands["read"], NextState("READ")),
            If(self.csrs.o_get_buffer_space.re, NextState("GET_BUFFER_SPACE"))
        )
        fsm.act("WRITE",
            o_status_wait.eq(1),
            rt_packet.sr_stb.eq(1),
            If(rt_packet.sr_ack,
                NextValue(buffer_space, buffer_space - 1),
                If(buffer_space <= 1,
                    NextState("GET_BUFFER_SPACE")
                ).Else(
                    NextState("IDLE")
                )
            )
        )
        fsm.act("GET_BUFFER_SPACE",
            o_status_wait.eq(1),
            rt_packet.buffer_space_not_ack.eq(1),
            rt_packet_buffer_request.eq(1),
            rt_packet.sr_stb.eq(1),
            If(rt_packet.sr_ack,
                NextState("GET_BUFFER_SPACE_REPLY")
            )
        )
        fsm.act("GET_BUFFER_SPACE_REPLY",
            o_status_wait.eq(1),
            NextValue(buffer_space, rt_packet.buffer_space),
            rt_packet.buffer_space_not_ack.eq(1),
            If(rt_packet.buffer_space_not,
               If(rt_packet.buffer_space != 0,
                    NextState("IDLE")
                ).Else(
                    NextState("GET_BUFFER_SPACE")
                )
            ),
            timeout_counter.wait.eq(1),
            If(timeout_counter.done,
                signal_buffer_space_timeout.eq(1),
                NextState("GET_BUFFER_SPACE")
            )
        )
        fsm.act("READ",
            i_status_wait_status.eq(1),
            rt_packet.read_not_ack.eq(1),
            rt_packet_read_request.eq(1),
            rt_packet.sr_stb.eq(1),
            If(rt_packet.sr_ack,
                NextState("GET_READ_REPLY")
            )
        )
        fsm.act("GET_READ_REPLY",
            i_status_wait_status.eq(1),
            rt_packet.read_not_ack.eq(1),
            If(rt_packet.read_not,
                load_read_reply.eq(1),
                NextState("IDLE")
            )
        )

        # debug CSRs
        self.comb += self.csrs.o_dbg_buffer_space.status.eq(buffer_space),
        self.sync += \
            If((rt_packet.sr_stb & rt_packet.sr_ack & rt_packet_buffer_request),
               self.csrs.o_dbg_buffer_space_req_cnt.status.eq(
                   self.csrs.o_dbg_buffer_space_req_cnt.status + 1)
            )

    def get_csrs(self):
        return self.csrs.get_csrs()


class RTManager(Module, AutoCSR):
    def __init__(self, rt_packet):
        self.request_echo = CSR()

        self.update_packet_cnt = CSR()
        self.packet_cnt_tx = CSRStatus(32)
        self.packet_cnt_rx = CSRStatus(32)

        # # #

        self.comb += self.request_echo.w.eq(rt_packet.echo_stb)
        self.sync += [
            If(rt_packet.echo_ack, rt_packet.echo_stb.eq(0)),
            If(self.request_echo.re, rt_packet.echo_stb.eq(1))
        ]

        self.sync += \
            If(self.update_packet_cnt.re,
                self.packet_cnt_tx.status.eq(rt_packet.packet_cnt_tx),
                self.packet_cnt_rx.status.eq(rt_packet.packet_cnt_rx)
            )
