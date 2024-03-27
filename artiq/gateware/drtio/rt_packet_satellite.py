"""Real-time packet layer for satellites"""

from migen import *
from migen.genlib.fsm import *
from migen.genlib.misc import WaitTimer

from artiq.gateware.rtio import cri
from artiq.gateware.drtio.rt_serializer import *


class RTPacketSatellite(Module):
    def __init__(self, link_layer, interface=None):
        self.reset = Signal()

        self.unknown_packet_type = Signal()
        self.packet_truncated = Signal()
        self.buffer_space_timeout = Signal()

        self.tsc_load = Signal()
        self.tsc_load_value = Signal(64)

        if interface is None:
            interface = cri.Interface()
        self.cri = interface

        # # #

        # RX/TX datapath
        assert len(link_layer.tx_rt_data) == len(link_layer.rx_rt_data)
        assert len(link_layer.tx_rt_data) % 8 == 0
        ws = len(link_layer.tx_rt_data)
        rx_plm = get_m2s_layouts(ws)
        rx_dp = ReceiveDatapath(
            link_layer.rx_rt_frame, link_layer.rx_rt_data, rx_plm)
        self.submodules += rx_dp
        tx_plm = get_s2m_layouts(ws)
        tx_dp = TransmitDatapath(
            link_layer.tx_rt_frame, link_layer.tx_rt_data, tx_plm)
        self.submodules += tx_dp

        # RX write data buffer
        write_data_buffer_load = Signal()
        write_data_buffer_cnt = Signal(max=512//ws+1)
        write_data_buffer = Signal(512)
        self.sync += \
            If(write_data_buffer_load,
                Case(write_data_buffer_cnt,
                     {i: write_data_buffer[i*ws:(i+1)*ws].eq(rx_dp.data_r)
                      for i in range(512//ws)}),
                write_data_buffer_cnt.eq(write_data_buffer_cnt + 1)
            ).Else(
                write_data_buffer_cnt.eq(0)
            )

        # RX->TX
        echo_req = Signal()
        buffer_space_set = Signal()
        buffer_space_req = Signal()
        buffer_space_ack = Signal()
        self.sync += [
            If(buffer_space_ack, buffer_space_req.eq(0)),
            If(buffer_space_set, buffer_space_req.eq(1)),
        ]

        buffer_space_update = Signal()
        buffer_space = Signal(16)
        self.sync += If(buffer_space_update, buffer_space.eq(self.cri.o_buffer_space))

        load_read_request = Signal()
        clear_read_request = Signal()
        read_request_pending = Signal()
        self.sync += [
            If(clear_read_request | self.reset,
                read_request_pending.eq(0)
            ),
            If(load_read_request,
                read_request_pending.eq(1),
            )
        ]

        # RX FSM
        cri_read = Signal()
        cri_buffer_space = Signal()
        self.comb += [
            self.tsc_load_value.eq(
                rx_dp.packet_as["set_time"].timestamp),
            If(cri_read | read_request_pending,
                self.cri.chan_sel.eq(
                    rx_dp.packet_as["read_request"].chan_sel),
            ).Elif(cri_buffer_space,
                self.cri.chan_sel.eq(
                    rx_dp.packet_as["buffer_space_request"].destination << 16)
            ).Else(
                self.cri.chan_sel.eq(
                    rx_dp.packet_as["write"].chan_sel),
            ),
            self.cri.i_timeout.eq(
                rx_dp.packet_as["read_request"].timeout),
            self.cri.o_timestamp.eq(
                rx_dp.packet_as["write"].timestamp),
            self.cri.o_address.eq(
                rx_dp.packet_as["write"].address),
            self.cri.o_data.eq(
                Cat(rx_dp.packet_as["write"].short_data, write_data_buffer)),
        ]

        rx_fsm = FSM(reset_state="INPUT")
        self.submodules += rx_fsm

        ongoing_packet_next = Signal()
        ongoing_packet = Signal()
        self.sync += ongoing_packet.eq(ongoing_packet_next)

        timeout_counter = WaitTimer(8191)
        self.submodules += timeout_counter

        rx_fsm.act("INPUT",
            If(rx_dp.frame_r,
                rx_dp.packet_buffer_load.eq(1),
                If(rx_dp.packet_last,
                    Case(rx_dp.packet_type, {
                        # echo must have fixed latency, so there is no memory
                        # mechanism
                        rx_plm.types["echo_request"]: echo_req.eq(1),
                        rx_plm.types["set_time"]: NextState("SET_TIME"),
                        rx_plm.types["write"]: NextState("WRITE"),
                        rx_plm.types["buffer_space_request"]: NextState("BUFFER_SPACE_REQUEST"),
                        rx_plm.types["read_request"]: NextState("READ_REQUEST"),
                        "default": self.unknown_packet_type.eq(1)
                    })
                ).Else(
                    ongoing_packet_next.eq(1)
                ),
                If(~rx_dp.frame_r & ongoing_packet,
                    self.packet_truncated.eq(1)
                )
            )
        )
        rx_fsm.act("SET_TIME",
            self.tsc_load.eq(1),
            NextState("INPUT")
        )

        # CRI mux defaults to write information
        rx_fsm.act("WRITE",
            If(write_data_buffer_cnt == rx_dp.packet_as["write"].extra_data_cnt,
                NextState("WRITE_CMD")
            ).Else(
                write_data_buffer_load.eq(1),
                If(~rx_dp.frame_r,
                    self.packet_truncated.eq(1),
                    NextState("INPUT")
                )
            )
        )
        rx_fsm.act("WRITE_CMD",
            self.cri.cmd.eq(cri.commands["write"]),
            NextState("INPUT")
        )

        rx_fsm.act("BUFFER_SPACE_REQUEST",
            cri_buffer_space.eq(1),
            NextState("BUFFER_SPACE_REQUEST_CMD")
        )
        rx_fsm.act("BUFFER_SPACE_REQUEST_CMD",
            cri_buffer_space.eq(1),
            self.cri.cmd.eq(cri.commands["get_buffer_space"]),
            NextState("BUFFER_SPACE")
        )
        rx_fsm.act("BUFFER_SPACE",
            cri_buffer_space.eq(1),
            timeout_counter.wait.eq(1),
            If(timeout_counter.done,
                self.buffer_space_timeout.eq(1),
                NextState("INPUT")
            ).Elif(self.cri.o_buffer_space_valid,
                buffer_space_set.eq(1),
                buffer_space_update.eq(1),
                NextState("INPUT")
            )
        )

        rx_fsm.act("READ_REQUEST",
            cri_read.eq(1),
            NextState("READ_REQUEST_CMD")
        )
        rx_fsm.act("READ_REQUEST_CMD",
            load_read_request.eq(1),
            cri_read.eq(1),
            self.cri.cmd.eq(cri.commands["read"]),
            NextState("INPUT")
        )

        # TX FSM
        tx_fsm = FSM(reset_state="IDLE")
        self.submodules += tx_fsm

        tx_fsm.act("IDLE",
            If(echo_req, NextState("ECHO")),
            If(buffer_space_req, NextState("BUFFER_SPACE")),
            If(read_request_pending & ~self.cri.i_status[2],
                NextState("READ"),
                If(self.cri.i_status[0], NextState("READ_TIMEOUT")),
                If(self.cri.i_status[1], NextState("READ_OVERFLOW"))
            )
        )

        tx_fsm.act("ECHO",
            tx_dp.send("echo_reply"),
            If(tx_dp.packet_last, NextState("IDLE"))
        )

        tx_fsm.act("BUFFER_SPACE",
            buffer_space_ack.eq(1),
            tx_dp.send("buffer_space_reply", space=buffer_space),
            If(tx_dp.packet_last, NextState("IDLE"))
        )

        tx_fsm.act("READ_TIMEOUT",
            tx_dp.send("read_reply_noevent", overflow=0),
            clear_read_request.eq(1),
            If(tx_dp.packet_last, NextState("IDLE"))
        )
        tx_fsm.act("READ_OVERFLOW",
            tx_dp.send("read_reply_noevent", overflow=1),
            clear_read_request.eq(1),
            If(tx_dp.packet_last, NextState("IDLE"))
        )
        tx_fsm.act("READ",
            tx_dp.send("read_reply",
                       timestamp=self.cri.i_timestamp,
                       data=self.cri.i_data),
            If(tx_dp.packet_last,
                clear_read_request.eq(1),
                NextState("IDLE")
            )
        )
