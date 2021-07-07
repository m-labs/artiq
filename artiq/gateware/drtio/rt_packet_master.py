"""Real-time packet layer for masters"""

from migen import *
from migen.genlib.fsm import *
from migen.genlib.fifo import AsyncFIFO
from migen.genlib.cdc import BlindTransfer

from artiq.gateware.rtio.cdc import GrayCodeTransfer
from artiq.gateware.drtio.cdc import CrossDomainRequest, CrossDomainNotification
from artiq.gateware.drtio.rt_serializer import *


class RTPacketMaster(Module):
    def __init__(self, link_layer, sr_fifo_depth=4):
        # all interface signals in sys domain unless otherwise specified

        # standard request interface
        #
        # notwrite=1 address=0  buffer space request <destination>
        # notwrite=1 address=1  read request <channel, timestamp>
        #
        # optimized for write throughput
        # requests are performed on the DRTIO link preserving their order of issue
        # this is important for buffer space requests, which have to be ordered
        # wrt writes.
        self.sr_stb = Signal()
        self.sr_ack = Signal()
        self.sr_notwrite = Signal()
        self.sr_timestamp = Signal(64)
        self.sr_chan_sel = Signal(24)
        self.sr_address = Signal(8)
        self.sr_data = Signal(512)

        # buffer space reply interface
        self.buffer_space_not = Signal()
        self.buffer_space_not_ack = Signal()
        self.buffer_space = Signal(16)

        # read reply interface
        self.read_not = Signal()
        self.read_not_ack = Signal()
        #  no_event   is_overflow
        #     0            X       event
        #     1            0       timeout
        #     1            1       overflow
        self.read_no_event = Signal()
        self.read_is_overflow = Signal()
        self.read_data = Signal(32)
        self.read_timestamp = Signal(64)

        # echo interface
        self.echo_stb = Signal()
        self.echo_ack = Signal()
        self.echo_sent_now = Signal()  # in rtio domain
        self.echo_received_now = Signal()  # in rtio_rx domain

        # set_time interface
        self.set_time_stb = Signal()
        self.set_time_ack = Signal()
        # in rtio domain, must be valid all time while there is
        # a set_time request pending
        self.tsc_value = Signal(64)

        # rx errors
        self.err_unknown_packet_type = Signal()
        self.err_packet_truncated = Signal()

        # packet counters
        self.packet_cnt_tx = Signal(32)
        self.packet_cnt_rx = Signal(32)

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

        # Write FIFO and extra data count
        sr_fifo = ClockDomainsRenamer({"write": "sys", "read": "rtio"})(
            AsyncFIFO(1+64+24+8+512, sr_fifo_depth))
        self.submodules += sr_fifo
        sr_notwrite_d = Signal()
        sr_timestamp_d = Signal(64)
        sr_chan_sel_d = Signal(24)
        sr_address_d = Signal(8)
        sr_data_d = Signal(512)
        self.comb += [
            sr_fifo.we.eq(self.sr_stb),
            self.sr_ack.eq(sr_fifo.writable),
            sr_fifo.din.eq(Cat(self.sr_notwrite, self.sr_timestamp, self.sr_chan_sel,
                               self.sr_address, self.sr_data)),
            Cat(sr_notwrite_d, sr_timestamp_d, sr_chan_sel_d,
                sr_address_d, sr_data_d).eq(sr_fifo.dout)
        ]

        sr_buf_readable = Signal()
        sr_buf_re = Signal()

        self.comb += sr_fifo.re.eq(sr_fifo.readable & (~sr_buf_readable | sr_buf_re))
        self.sync.rtio += \
            If(sr_fifo.re,
                sr_buf_readable.eq(1),
            ).Elif(sr_buf_re,
                sr_buf_readable.eq(0),
            )

        sr_notwrite = Signal()
        sr_timestamp = Signal(64)
        sr_chan_sel = Signal(24)
        sr_address = Signal(8)
        sr_extra_data_cnt = Signal(8)
        sr_data = Signal(512)

        self.sync.rtio += If(sr_fifo.re,
            sr_notwrite.eq(sr_notwrite_d),
            sr_timestamp.eq(sr_timestamp_d),
            sr_chan_sel.eq(sr_chan_sel_d),
            sr_address.eq(sr_address_d),
            sr_data.eq(sr_data_d))

        short_data_len = tx_plm.field_length("write", "short_data")
        sr_extra_data_d = Signal(512)
        self.comb += sr_extra_data_d.eq(sr_data_d[short_data_len:])
        for i in range(512//ws):
            self.sync.rtio += If(sr_fifo.re,
                If(sr_extra_data_d[ws*i:ws*(i+1)] != 0, sr_extra_data_cnt.eq(i+1)))

        sr_extra_data = Signal(512)
        self.sync.rtio += If(sr_fifo.re, sr_extra_data.eq(sr_extra_data_d))

        extra_data_ce = Signal()
        extra_data_last = Signal()
        extra_data_counter = Signal(max=512//ws+1)
        self.comb += [
            Case(extra_data_counter, 
                {i+1: tx_dp.raw_data.eq(sr_extra_data[i*ws:(i+1)*ws])
                 for i in range(512//ws)}),
            extra_data_last.eq(extra_data_counter == sr_extra_data_cnt)
        ]
        self.sync.rtio += \
            If(extra_data_ce,
                extra_data_counter.eq(extra_data_counter + 1),
            ).Else(
                extra_data_counter.eq(1)
            )

        # CDC
        buffer_space_not = Signal()
        buffer_space = Signal(16)
        self.submodules += CrossDomainNotification("rtio_rx", "sys",
            buffer_space_not, buffer_space,
            self.buffer_space_not, self.buffer_space_not_ack, self.buffer_space)

        set_time_stb = Signal()
        set_time_ack = Signal()
        self.submodules += CrossDomainRequest("rtio",
            self.set_time_stb, self.set_time_ack, None,
            set_time_stb, set_time_ack, None)

        echo_stb = Signal()
        echo_ack = Signal()
        self.submodules += CrossDomainRequest("rtio",
            self.echo_stb, self.echo_ack, None,
            echo_stb, echo_ack, None)

        read_not = Signal()
        read_no_event = Signal()
        read_is_overflow = Signal()
        read_data = Signal(32)
        read_timestamp = Signal(64)
        self.submodules += CrossDomainNotification("rtio_rx", "sys",
            read_not,
            Cat(read_no_event, read_is_overflow, read_data, read_timestamp),

            self.read_not, self.read_not_ack,
            Cat(self.read_no_event, self.read_is_overflow,
                self.read_data, self.read_timestamp))
        self.comb += [
            read_is_overflow.eq(rx_dp.packet_as["read_reply_noevent"].overflow),
            read_data.eq(rx_dp.packet_as["read_reply"].data),
            read_timestamp.eq(rx_dp.packet_as["read_reply"].timestamp)
        ]

        err_unknown_packet_type = BlindTransfer("rtio_rx", "sys")
        err_packet_truncated = BlindTransfer("rtio_rx", "sys")
        self.submodules += err_unknown_packet_type, err_packet_truncated
        self.comb += [
            self.err_unknown_packet_type.eq(err_unknown_packet_type.o),
            self.err_packet_truncated.eq(err_packet_truncated.o)
        ]

        # TX FSM
        tx_fsm = ClockDomainsRenamer("rtio")(FSM(reset_state="IDLE"))
        self.submodules += tx_fsm

        echo_sent_now = Signal()
        self.sync.rtio += self.echo_sent_now.eq(echo_sent_now)
        tsc_value = Signal(64)
        tsc_value_load = Signal()
        self.sync.rtio += If(tsc_value_load, tsc_value.eq(self.tsc_value))

        tx_fsm.act("IDLE",
            # Ensure 2 cycles between frames on the link.
            NextState("READY")
        )
        tx_fsm.act("READY",
            If(sr_buf_readable,
                If(sr_notwrite,
                    Case(sr_address[0], {
                        0: NextState("BUFFER_SPACE"),
                        1: NextState("READ")
                    }),
                ).Else(
                    NextState("WRITE")
                )
            ).Else(
                If(echo_stb,
                    echo_sent_now.eq(1),
                    NextState("ECHO")
                ).Elif(set_time_stb,
                    tsc_value_load.eq(1),
                    NextState("SET_TIME")
                )
            )
        )
        tx_fsm.act("WRITE",
            tx_dp.send("write",
                timestamp=sr_timestamp,
                chan_sel=sr_chan_sel,
                address=sr_address,
                extra_data_cnt=sr_extra_data_cnt,
                short_data=sr_data[:short_data_len]),
            If(tx_dp.packet_last,
                If(sr_extra_data_cnt == 0,
                    sr_buf_re.eq(1),
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
                sr_buf_re.eq(1),
                NextState("IDLE")
            )
        )
        tx_fsm.act("BUFFER_SPACE",
            tx_dp.send("buffer_space_request", destination=sr_chan_sel[16:]),
            If(tx_dp.packet_last,
                sr_buf_re.eq(1),
                NextState("IDLE")
            )
        )
        tx_fsm.act("READ",
            tx_dp.send("read_request", chan_sel=sr_chan_sel, timeout=sr_timestamp),
            If(tx_dp.packet_last,
                sr_buf_re.eq(1),
                NextState("IDLE")
            )
        )
        tx_fsm.act("ECHO",
            tx_dp.send("echo_request"),
            If(tx_dp.packet_last,
                echo_ack.eq(1),
                NextState("IDLE")
            )
        )
        tx_fsm.act("SET_TIME",
            tx_dp.send("set_time", timestamp=tsc_value),
            If(tx_dp.packet_last,
                set_time_ack.eq(1),
                NextState("IDLE")
            )
        )

        # RX FSM
        rx_fsm = ClockDomainsRenamer("rtio_rx")(FSM(reset_state="INPUT"))
        self.submodules += rx_fsm

        ongoing_packet_next = Signal()
        ongoing_packet = Signal()
        self.sync.rtio_rx += ongoing_packet.eq(ongoing_packet_next)

        echo_received_now = Signal()
        self.sync.rtio_rx += self.echo_received_now.eq(echo_received_now)

        rx_fsm.act("INPUT",
            If(rx_dp.frame_r,
                rx_dp.packet_buffer_load.eq(1),
                If(rx_dp.packet_last,
                    Case(rx_dp.packet_type, {
                        rx_plm.types["echo_reply"]: echo_received_now.eq(1),
                        rx_plm.types["buffer_space_reply"]: NextState("BUFFER_SPACE"),
                        rx_plm.types["read_reply"]: NextState("READ_REPLY"),
                        rx_plm.types["read_reply_noevent"]: NextState("READ_REPLY_NOEVENT"),
                        "default": err_unknown_packet_type.i.eq(1)
                    })
                ).Else(
                    ongoing_packet_next.eq(1)
                )
            ),
            If(~rx_dp.frame_r & ongoing_packet,
                err_packet_truncated.i.eq(1)
            )
        )
        rx_fsm.act("BUFFER_SPACE",
            buffer_space_not.eq(1),
            buffer_space.eq(rx_dp.packet_as["buffer_space_reply"].space),
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

        # packet counters
        tx_frame_r = Signal()
        packet_cnt_tx = Signal(32)
        self.sync.rtio += [
            tx_frame_r.eq(link_layer.tx_rt_frame),
            If(link_layer.tx_rt_frame & ~tx_frame_r,
                packet_cnt_tx.eq(packet_cnt_tx + 1))
        ]
        cdc_packet_cnt_tx = GrayCodeTransfer(32)
        self.submodules += cdc_packet_cnt_tx
        self.comb += [
            cdc_packet_cnt_tx.i.eq(packet_cnt_tx),
            self.packet_cnt_tx.eq(cdc_packet_cnt_tx.o)
        ]

        rx_frame_r = Signal()
        packet_cnt_rx = Signal(32)
        self.sync.rtio_rx += [
            rx_frame_r.eq(link_layer.rx_rt_frame),
            If(link_layer.rx_rt_frame & ~rx_frame_r,
                packet_cnt_rx.eq(packet_cnt_rx + 1))
        ]
        cdc_packet_cnt_rx = ClockDomainsRenamer({"rtio": "rtio_rx"})(
            GrayCodeTransfer(32))
        self.submodules += cdc_packet_cnt_rx
        self.comb += [
            cdc_packet_cnt_rx.i.eq(packet_cnt_rx),
            self.packet_cnt_rx.eq(cdc_packet_cnt_rx.o)
        ]
