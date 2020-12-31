"""Real-time controller for master"""

from migen import *
from migen.genlib.cdc import MultiReg
from migen.genlib.misc import WaitTimer

from misoc.interconnect.csr import *

from artiq.gateware.rtio import cri


class _CSRs(AutoCSR):
    def __init__(self):
        self.reset = CSRStorage()

        self.protocol_error = CSR(3)

        self.set_time = CSR()
        self.underflow_margin = CSRStorage(16, reset=300)

        self.force_destination = CSRStorage()
        self.destination = CSRStorage(8)

        self.o_get_buffer_space = CSR()
        self.o_dbg_buffer_space = CSRStatus(16)
        self.o_dbg_buffer_space_req_cnt = CSRStatus(32)
        self.o_wait = CSRStatus()


class RTController(Module):
    def __init__(self, tsc, rt_packet):
        self.csrs = _CSRs()
        self.cri = cri.Interface()

        # protocol errors
        err_unknown_packet_type = Signal()
        err_packet_truncated = Signal()
        signal_buffer_space_timeout = Signal()
        err_buffer_space_timeout = Signal()
        self.sync += [
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

        # TSC synchronization
        self.comb += [
            rt_packet.tsc_value.eq(tsc.coarse_ts),
            self.csrs.set_time.w.eq(rt_packet.set_time_stb)
        ]
        self.sync += [
            If(rt_packet.set_time_ack, rt_packet.set_time_stb.eq(0)),
            If(self.csrs.set_time.re, rt_packet.set_time_stb.eq(1))
        ]

        # chan_sel forcing
        chan_sel = Signal(24)
        self.comb += chan_sel.eq(Mux(self.csrs.force_destination.storage,
            self.csrs.destination.storage << 16,
            self.cri.chan_sel))

        # common packet fields
        rt_packet_buffer_request = Signal()
        rt_packet_read_request = Signal()
        self.comb += [
            rt_packet.sr_chan_sel.eq(chan_sel),
            rt_packet.sr_address.eq(self.cri.o_address),
            rt_packet.sr_data.eq(self.cri.o_data),
            If(rt_packet_read_request,
                rt_packet.sr_timestamp.eq(self.cri.i_timeout)
            ).Else(
                rt_packet.sr_timestamp.eq(self.cri.o_timestamp)
            ),
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
            self.cri.o_status.eq(Cat(o_status_wait, o_status_underflow)),
            self.csrs.o_wait.status.eq(o_status_wait)
        ]
        o_underflow_set = Signal()
        self.sync += [
            If(self.cri.cmd == cri.commands["write"],
                o_status_underflow.eq(0)
            ),
            If(o_underflow_set, o_status_underflow.eq(1))
        ]

        timeout_counter = WaitTimer(8191)
        self.submodules += timeout_counter

        cond_underflow = Signal()
        self.comb += cond_underflow.eq((self.cri.o_timestamp[tsc.glbl_fine_ts_width:]
                           - self.csrs.underflow_margin.storage[tsc.glbl_fine_ts_width:]) < tsc.coarse_ts_sys)

        # buffer space
        buffer_space = Memory(16, 256)
        buffer_space_port = buffer_space.get_port(write_capable=True)
        self.specials += buffer_space, buffer_space_port

        buffer_space_load = Signal()
        buffer_space_dec = Signal()
        self.comb += [
            buffer_space_port.adr.eq(chan_sel[16:]),
            buffer_space_port.we.eq(buffer_space_load | buffer_space_dec),
            If(buffer_space_load,
                buffer_space_port.dat_w.eq(rt_packet.buffer_space)
            ).Else(
                buffer_space_port.dat_w.eq(buffer_space_port.dat_r - 1)
            )
        ]

        # input status
        i_status_wait_event = Signal()
        i_status_overflow = Signal()
        i_status_wait_status = Signal()
        self.comb += self.cri.i_status.eq(Cat(
            i_status_wait_event, i_status_overflow, i_status_wait_status))

        load_read_reply = Signal()
        self.sync += [
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
        fsm = FSM()
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
                buffer_space_dec.eq(1),
                If(buffer_space_port.dat_r <= 1,
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
            buffer_space_load.eq(1),
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
                NextState("IDLE")
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
            If(self.csrs.reset.storage | rt_packet.read_not,
                load_read_reply.eq(1),
                NextState("IDLE")
            )
        )

        # debug CSRs
        self.comb += self.csrs.o_dbg_buffer_space.status.eq(buffer_space_port.dat_r),
        self.sync += \
            If((rt_packet.sr_stb & rt_packet.sr_ack & rt_packet_buffer_request),
               self.csrs.o_dbg_buffer_space_req_cnt.status.eq(
                   self.csrs.o_dbg_buffer_space_req_cnt.status + 1)
            )

    def get_csrs(self):
        return self.csrs.get_csrs()
