from migen import *
from migen.genlib.fsm import *
from migen.genlib.misc import WaitTimer


from artiq.gateware.rtio import cri
from artiq.gateware.drtio.cdc import CrossDomainNotification
from artiq.gateware.drtio.rt_serializer import *


class RTPacketRepeater(Module):
    def __init__(self, tsc, link_layer):
        # in rtio domain
        self.reset = Signal()

        # CRI target interface in rtio domain
        self.cri = cri.Interface()

        # in rtio_rx domain
        self.err_unknown_packet_type = Signal()
        self.err_packet_truncated = Signal()

        # in rtio domain
        self.err_command_missed = Signal()
        self.command_missed_cmd = Signal(2)
        self.command_missed_chan_sel = Signal(24)
        self.err_buffer_space_timeout = Signal()
        self.buffer_space_destination = Signal(8)

        # set_time interface, in rtio domain
        self.set_time_stb = Signal()
        self.set_time_ack = Signal()

        # # #

        # RX/TX datapath
        assert len(link_layer.tx_rt_data) == len(link_layer.rx_rt_data)
        assert len(link_layer.tx_rt_data) % 8 == 0
        ws = len(link_layer.tx_rt_data)
        tx_plm = get_m2s_layouts(ws)
        tx_dp = ClockDomainsRenamer("rtio")(TransmitDatapath(
            link_layer.tx_rt_frame, link_layer.tx_rt_data, tx_plm))
        self.submodules += tx_dp
        rx_plm = get_s2m_layouts(ws)
        rx_dp = ClockDomainsRenamer("rtio_rx")(ReceiveDatapath(
            link_layer.rx_rt_frame, link_layer.rx_rt_data, rx_plm))
        self.submodules += rx_dp

        # TSC sync
        tsc_value = Signal(64)
        tsc_value_load = Signal()
        self.sync.rtio += If(tsc_value_load, tsc_value.eq(tsc.coarse_ts))

        # CRI buffer stage 1
        cb0_loaded = Signal()
        cb0_ack = Signal()

        cb0_cmd = Signal(2)
        cb0_timestamp = Signal(64)
        cb0_chan_sel = Signal(24)
        cb0_o_address = Signal(8)
        cb0_o_data = Signal(512)
        self.sync.rtio += [
            If(self.reset | cb0_ack,
                cb0_loaded.eq(0),
                cb0_cmd.eq(cri.commands["nop"])
            ),
            If(~self.reset & ~cb0_loaded & (self.cri.cmd != cri.commands["nop"]),
                cb0_loaded.eq(1),
                cb0_cmd.eq(self.cri.cmd),
                If(self.cri.cmd == cri.commands["read"],
                    cb0_timestamp.eq(self.cri.i_timeout)
                ).Else(
                    cb0_timestamp.eq(self.cri.o_timestamp)
                ),
                cb0_chan_sel.eq(self.cri.chan_sel),
                cb0_o_address.eq(self.cri.o_address),
                cb0_o_data.eq(self.cri.o_data)
            ),
            self.err_command_missed.eq(cb0_loaded & (self.cri.cmd != cri.commands["nop"])),
            self.command_missed_chan_sel.eq(self.cri.chan_sel),
            self.command_missed_cmd.eq(self.cri.cmd)
        ]

        # CRI buffer stage 2 and write data slicer
        cb_loaded = Signal()
        cb_ack = Signal()

        cb_cmd = Signal(2)
        cb_timestamp = Signal(64)
        cb_chan_sel = Signal(24)
        cb_o_address = Signal(8)
        cb_o_data = Signal(512)
        self.sync.rtio += [
            If(self.reset | cb_ack,
                cb_loaded.eq(0),
                cb_cmd.eq(cri.commands["nop"])
            ),
            If(~self.reset & ~cb_loaded & cb0_loaded,
                cb_loaded.eq(1),
                cb_cmd.eq(cb0_cmd),
                cb_timestamp.eq(cb0_timestamp),
                cb_chan_sel.eq(cb0_chan_sel),
                cb_o_address.eq(cb0_o_address),
                cb_o_data.eq(cb0_o_data)
            )
        ]
        self.comb += cb0_ack.eq(~cb_loaded)

        wb_extra_data_cnt = Signal(8)
        short_data_len = tx_plm.field_length("write", "short_data")
        wb_extra_data_a = Signal(512)
        self.comb += wb_extra_data_a.eq(self.cri.o_data[short_data_len:])
        for i in range(512//ws):
            self.sync.rtio += If(self.cri.cmd == cri.commands["write"],
                If(wb_extra_data_a[ws*i:ws*(i+1)] != 0, wb_extra_data_cnt.eq(i+1)))

        wb_extra_data = Signal(512)
        self.sync.rtio += If(self.cri.cmd == cri.commands["write"],
            wb_extra_data.eq(wb_extra_data_a))

        extra_data_ce = Signal()
        extra_data_last = Signal()
        extra_data_counter = Signal(max=512//ws+1)
        self.comb += [
            Case(extra_data_counter, 
                {i+1: tx_dp.raw_data.eq(wb_extra_data[i*ws:(i+1)*ws])
                 for i in range(512//ws)}),
            extra_data_last.eq(extra_data_counter == wb_extra_data_cnt)
        ]
        self.sync.rtio += \
            If(extra_data_ce,
                extra_data_counter.eq(extra_data_counter + 1),
            ).Else(
                extra_data_counter.eq(1)
            )

        # Buffer space
        self.sync.rtio += If(self.cri.cmd == cri.commands["get_buffer_space"],
            self.buffer_space_destination.eq(self.cri.chan_sel[16:]))

        rx_buffer_space_not = Signal()
        rx_buffer_space = Signal(16)
        buffer_space_not = Signal()
        buffer_space_not_ack = Signal()
        self.submodules += CrossDomainNotification("rtio_rx", "rtio",
            rx_buffer_space_not, rx_buffer_space,
            buffer_space_not, buffer_space_not_ack,
            self.cri.o_buffer_space)

        timeout_counter = ClockDomainsRenamer("rtio")(WaitTimer(8191))
        self.submodules += timeout_counter

        # Read
        read_not = Signal()
        read_no_event = Signal()
        read_is_overflow = Signal()
        read_data = Signal(32)
        read_timestamp = Signal(64)
        rtio_read_not = Signal()
        rtio_read_not_ack = Signal()
        rtio_read_no_event = Signal()
        rtio_read_is_overflow = Signal()
        rtio_read_data = Signal(32)
        rtio_read_timestamp = Signal(64)
        self.submodules += CrossDomainNotification("rtio_rx", "rtio",
            read_not,
            Cat(read_no_event, read_is_overflow, read_data, read_timestamp),

            rtio_read_not, rtio_read_not_ack,
            Cat(rtio_read_no_event, rtio_read_is_overflow,
                rtio_read_data, rtio_read_timestamp))
        self.comb += [
            read_is_overflow.eq(rx_dp.packet_as["read_reply_noevent"].overflow),
            read_data.eq(rx_dp.packet_as["read_reply"].data),
            read_timestamp.eq(rx_dp.packet_as["read_reply"].timestamp)
        ]

        # input status
        i_status_wait_event = Signal()
        i_status_overflow = Signal()
        self.comb += self.cri.i_status.eq(Cat(
            i_status_wait_event, i_status_overflow, cb0_loaded | cb_loaded))

        load_read_reply = Signal()
        self.sync.rtio += [
            If(load_read_reply,
                i_status_wait_event.eq(0),
                i_status_overflow.eq(0),
                If(rtio_read_no_event,
                    If(rtio_read_is_overflow,
                        i_status_overflow.eq(1)
                    ).Else(
                        i_status_wait_event.eq(1)
                    )
                ),
                self.cri.i_data.eq(rtio_read_data),
                self.cri.i_timestamp.eq(rtio_read_timestamp)
            )
        ]

        # TX and CRI FSM
        tx_fsm = ClockDomainsRenamer("rtio")(FSM(reset_state="IDLE"))
        self.submodules += tx_fsm

        tx_fsm.act("IDLE",
            # Ensure 2 cycles between frames on the link.
            NextState("READY")
        )
        tx_fsm.act("READY",
            If(self.set_time_stb,
                tsc_value_load.eq(1),
                NextState("SET_TIME")
            ).Else(
                If(cb_cmd == cri.commands["write"], NextState("WRITE")),
                If(cb_cmd == cri.commands["get_buffer_space"], NextState("BUFFER_SPACE")),
                If(cb_cmd == cri.commands["read"], NextState("READ"))
            )
        )

        tx_fsm.act("SET_TIME",
            tx_dp.send("set_time", timestamp=tsc_value),
            If(tx_dp.packet_last,
                self.set_time_ack.eq(1),
                NextState("IDLE")
            )
        )

        tx_fsm.act("WRITE",
            tx_dp.send("write",
                timestamp=cb_timestamp,
                chan_sel=cb_chan_sel,
                address=cb_o_address,
                extra_data_cnt=wb_extra_data_cnt,
                short_data=cb_o_data[:short_data_len]),
            If(tx_dp.packet_last,
                If(wb_extra_data_cnt == 0,
                    cb_ack.eq(1),
                    NextState("IDLE")
                ).Else(
                    NextState("WRITE_EXTRA")
                )
            )
        )
        tx_fsm.act("WRITE_EXTRA",
            tx_dp.raw_stb.eq(1),
            extra_data_ce.eq(1),
            If(extra_data_last,
                cb_ack.eq(1),
                NextState("IDLE")
            )
        )

        tx_fsm.act("BUFFER_SPACE",
            tx_dp.send("buffer_space_request", destination=self.buffer_space_destination),
            If(tx_dp.packet_last,
                buffer_space_not_ack.eq(1),
                NextState("GET_BUFFER_SPACE_REPLY")
            )
        )
        tx_fsm.act("GET_BUFFER_SPACE_REPLY",
            timeout_counter.wait.eq(1),
            If(timeout_counter.done,
                self.err_buffer_space_timeout.eq(1),
                cb_ack.eq(1),
                NextState("READY")
            ).Else(
                If(buffer_space_not,
                    self.cri.o_buffer_space_valid.eq(1),
                    cb_ack.eq(1),
                    NextState("READY")
                ),
            )
        )

        tx_fsm.act("READ",
            tx_dp.send("read_request",
                chan_sel=cb_chan_sel,
                timeout=cb_timestamp),
            rtio_read_not_ack.eq(1),
            If(tx_dp.packet_last,
                NextState("GET_READ_REPLY")
            )
        )
        tx_fsm.act("GET_READ_REPLY",
            rtio_read_not_ack.eq(1),
            If(self.reset | rtio_read_not,
                load_read_reply.eq(1),
                cb_ack.eq(1),
                NextState("READY")
            )
        )

        # RX FSM
        rx_fsm = ClockDomainsRenamer("rtio_rx")(FSM(reset_state="INPUT"))
        self.submodules += rx_fsm

        ongoing_packet_next = Signal()
        ongoing_packet = Signal()
        self.sync.rtio_rx += ongoing_packet.eq(ongoing_packet_next)

        rx_fsm.act("INPUT",
            If(rx_dp.frame_r,
                rx_dp.packet_buffer_load.eq(1),
                If(rx_dp.packet_last,
                    Case(rx_dp.packet_type, {
                        rx_plm.types["buffer_space_reply"]: NextState("BUFFER_SPACE"),
                        rx_plm.types["read_reply"]: NextState("READ_REPLY"),
                        rx_plm.types["read_reply_noevent"]: NextState("READ_REPLY_NOEVENT"),
                        "default": self.err_unknown_packet_type.eq(1)
                    })
                ).Else(
                    ongoing_packet_next.eq(1)
                )
            ),
            If(~rx_dp.frame_r & ongoing_packet,
                self.err_packet_truncated.eq(1)
            )
        )
        rx_fsm.act("BUFFER_SPACE",
            rx_buffer_space_not.eq(1),
            rx_buffer_space.eq(rx_dp.packet_as["buffer_space_reply"].space),
            NextState("INPUT")
        )
        rx_fsm.act("READ_REPLY",
            read_not.eq(1),
            read_no_event.eq(0),
            NextState("INPUT")
        )
        rx_fsm.act("READ_REPLY_NOEVENT",
            read_not.eq(1),
            read_no_event.eq(1),
            NextState("INPUT")
        )
