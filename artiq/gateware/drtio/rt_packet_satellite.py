"""Real-time packet layer for satellites"""

from migen import *
from migen.genlib.fsm import *

from artiq.gateware.drtio.rt_serializer import *


class RTPacketSatellite(Module):
    def __init__(self, link_layer):
        self.unknown_packet_type = Signal()
        self.packet_truncated = Signal()

        self.tsc_load = Signal()
        self.tsc_load_value = Signal(64)
        self.tsc_input = Signal(64)

        self.reset = Signal(reset=1)
        self.reset_phy = Signal(reset=1)

        self.fifo_space_channel = Signal(16)
        self.fifo_space_update = Signal()
        self.fifo_space = Signal(16)

        # write parameters are stable one cycle before stb is asserted,
        # and when stb is asserted.
        self.write_stb = Signal()
        self.write_timestamp = Signal(64)
        self.write_channel = Signal(16)
        self.write_address = Signal(16)
        self.write_data = Signal(512)
        self.write_overflow = Signal()
        self.write_underflow = Signal()

        self.read_channel = Signal(16)
        self.read_readable = Signal()
        self.read_consume = Signal()
        self.read_data = Signal(32)
        self.read_timestamp = Signal(64)
        self.read_overflow = Signal()
        self.read_overflow_ack = Signal()

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
        fifo_space_set = Signal()
        fifo_space_req = Signal()
        fifo_space_ack = Signal()
        self.sync += [
            If(fifo_space_ack, fifo_space_req.eq(0)),
            If(fifo_space_set, fifo_space_req.eq(1)),
        ]

        # RX FSM
        self.comb += [
            self.tsc_load_value.eq(
                rx_dp.packet_as["set_time"].timestamp),
            self.fifo_space_channel.eq(
                rx_dp.packet_as["fifo_space_request"].channel),
            self.write_timestamp.eq(
                rx_dp.packet_as["write"].timestamp),
            self.write_channel.eq(
                rx_dp.packet_as["write"].channel),
            self.write_address.eq(
                rx_dp.packet_as["write"].address),
            self.write_data.eq(
                Cat(rx_dp.packet_as["write"].short_data, write_data_buffer)),
        ]

        reset = Signal()
        reset_phy = Signal()
        self.sync += [
            self.reset.eq(reset),
            self.reset_phy.eq(reset_phy)
        ]

        load_read_request = Signal()
        clear_read_request = Signal()
        read_request_pending = Signal()
        read_request_time_limit = Signal(64)
        read_request_timeout = Signal()
        read_request_wait = Signal()  # 1 cycle latency channel→(data,overflow) and time_limit→timeout
        self.sync += [
            If(clear_read_request | self.reset,
                read_request_pending.eq(0)
            ),
            read_request_wait.eq(0),
            If(load_read_request,
                read_request_pending.eq(1),
                read_request_wait.eq(1),
                self.read_channel.eq(rx_dp.packet_as["read_request"].channel),
                read_request_time_limit.eq(rx_dp.packet_as["read_request"].timeout)
            ),
            read_request_timeout.eq(self.tsc_input >= read_request_time_limit),
        ]

        rx_fsm = FSM(reset_state="INPUT")
        self.submodules += rx_fsm

        ongoing_packet_next = Signal()
        ongoing_packet = Signal()
        self.sync += ongoing_packet.eq(ongoing_packet_next)

        rx_fsm.act("INPUT",
            If(rx_dp.frame_r,
                rx_dp.packet_buffer_load.eq(1),
                If(rx_dp.packet_last,
                    Case(rx_dp.packet_type, {
                        # echo must have fixed latency, so there is no memory
                        # mechanism
                        rx_plm.types["echo_request"]: echo_req.eq(1),
                        rx_plm.types["set_time"]: NextState("SET_TIME"),
                        rx_plm.types["reset"]: NextState("RESET"),
                        rx_plm.types["write"]: NextState("WRITE"),
                        rx_plm.types["fifo_space_request"]: NextState("FIFO_SPACE"),
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
        rx_fsm.act("RESET",
            If(rx_dp.packet_as["reset"].phy,
                reset_phy.eq(1)
            ).Else(
                reset.eq(1)
            ),
            NextState("INPUT")
        )

        rx_fsm.act("WRITE",
            If(write_data_buffer_cnt == rx_dp.packet_as["write"].extra_data_cnt,
                self.write_stb.eq(1),
                NextState("INPUT")
            ).Else(
                write_data_buffer_load.eq(1),
                If(~rx_dp.frame_r,
                    self.packet_truncated.eq(1),
                    NextState("INPUT")
                )
            )
        )
        rx_fsm.act("FIFO_SPACE",
            fifo_space_set.eq(1),
            self.fifo_space_update.eq(1),
            NextState("INPUT")
        )

        rx_fsm.act("READ_REQUEST",
            load_read_request.eq(1),
            NextState("INPUT")
        )

        # TX FSM
        tx_fsm = FSM(reset_state="IDLE")
        self.submodules += tx_fsm

        tx_fsm.act("IDLE",
            If(echo_req, NextState("ECHO")),
            If(fifo_space_req, NextState("FIFO_SPACE")),
            If(~read_request_wait & read_request_pending,
                If(read_request_timeout, NextState("READ_TIMEOUT")),
                If(self.read_overflow, NextState("READ_OVERFLOW")),
                If(self.read_readable, NextState("READ"))
            )
        )

        tx_fsm.act("ECHO",
            tx_dp.send("echo_reply"),
            If(tx_dp.packet_last, NextState("IDLE"))
        )

        tx_fsm.act("FIFO_SPACE",
            fifo_space_ack.eq(1),
            tx_dp.send("fifo_space_reply", space=self.fifo_space),
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
            If(tx_dp.packet_last,
                self.read_overflow_ack.eq(1),
                NextState("IDLE")
            )
        )
        tx_fsm.act("READ",
            tx_dp.send("read_reply",
                       timestamp=self.read_timestamp,
                       data=self.read_data),
            clear_read_request.eq(1),
            If(tx_dp.packet_last,
                self.read_consume.eq(1),
                NextState("IDLE")
            )
        )
