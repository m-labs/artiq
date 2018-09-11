from migen import *
from migen.genlib.fsm import *
from migen.genlib.misc import WaitTimer


from artiq.gateware.rtio import cri
from artiq.gateware.drtio.cdc import CrossDomainNotification
from artiq.gateware.drtio.rt_serializer import *


class RTPacketRepeater(Module):
    def __init__(self, tsc, link_layer):
        # CRI target interface in rtio domain
        self.cri = cri.Interface()

        # in rtio_rx domain
        self.err_unknown_packet_type = Signal()
        self.err_packet_truncated = Signal()

        # in rtio domain
        self.err_command_missed = Signal()
        self.err_buffer_space_timeout = Signal()

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

        # Write buffer and extra data count
        wb_timestamp = Signal(64)
        wb_chan_sel = Signal(24)
        wb_address = Signal(16)
        wb_data = Signal(512)
        self.sync.rtio += If(self.cri.cmd == cri.commands["write"],
            wb_timestamp.eq(self.cri.timestamp),
            wb_chan_sel.eq(self.cri.chan_sel),
            wb_address.eq(self.cri.o_address),
            wb_data.eq(self.cri.o_data))

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
        buffer_space_destination = Signal(8)
        self.sync.rtio += If(self.cri.cmd == cri.commands["get_buffer_space"],
            buffer_space_destination.eq(self.cri.chan_sel[16:]))

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

        # Missed commands
        cri_ready = Signal()
        self.sync.rtio += self.err_command_missed.eq(~cri_ready & (self.cri.cmd != cri.commands["nop"]))

        # TX FSM
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
                cri_ready.eq(1),
                If(self.cri.cmd == cri.commands["write"], NextState("WRITE")),
                If(self.cri.cmd == cri.commands["get_buffer_space"], NextState("BUFFER_SPACE"))
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
                timestamp=wb_timestamp,
                chan_sel=wb_chan_sel,
                address=wb_address,
                extra_data_cnt=wb_extra_data_cnt,
                short_data=wb_data[:short_data_len]),
            If(tx_dp.packet_last,
                If(wb_extra_data_cnt == 0,
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
                NextState("IDLE")
            )
        )
        tx_fsm.act("BUFFER_SPACE",
            tx_dp.send("buffer_space_request", destination=buffer_space_destination),
            If(tx_dp.packet_last,
                buffer_space_not_ack.eq(1),
                NextState("WAIT_BUFFER_SPACE")
            )
        )
        tx_fsm.act("WAIT_BUFFER_SPACE",
            timeout_counter.wait.eq(1),
            If(timeout_counter.done,
                self.err_buffer_space_timeout.eq(1),
                NextState("IDLE")
            ).Else(
                If(buffer_space_not,
                    self.cri.o_buffer_space_valid.eq(1),
                    NextState("IDLE")
                ),
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
