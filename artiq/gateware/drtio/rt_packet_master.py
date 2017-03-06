"""Real-time packet layer for masters"""

from migen import *
from migen.genlib.fsm import *
from migen.genlib.fifo import AsyncFIFO
from migen.genlib.cdc import PulseSynchronizer

from artiq.gateware.rtio.cdc import GrayCodeTransfer
from artiq.gateware.drtio.rt_serializer import *


class _CrossDomainRequest(Module):
    def __init__(self, domain,
                 req_stb, req_ack, req_data,
                 srv_stb, srv_ack, srv_data):
        dsync = getattr(self.sync, domain)

        request = PulseSynchronizer("sys", domain)
        reply = PulseSynchronizer(domain, "sys")
        self.submodules += request, reply

        ongoing = Signal()
        self.comb += request.i.eq(~ongoing & req_stb)
        self.sync += [
            req_ack.eq(reply.o),
            If(req_stb, ongoing.eq(1)),
            If(req_ack, ongoing.eq(0))
        ]
        if req_data is not None:
            req_data_r = Signal.like(req_data)
            req_data_r.attr.add("no_retiming")
            self.sync += If(req_stb, req_data_r.eq(req_data))
        dsync += [
            If(request.o, srv_stb.eq(1)),
            If(srv_ack, srv_stb.eq(0))
        ]
        if req_data is not None:
            dsync += If(request.o, srv_data.eq(req_data_r))
        self.comb += reply.i.eq(srv_stb & srv_ack)


class _CrossDomainNotification(Module):
    def __init__(self, domain,
                 emi_stb, emi_data,
                 rec_stb, rec_ack, rec_data):
        emi_data_r = Signal.like(emi_data)
        emi_data_r.attr.add("no_retiming")
        dsync = getattr(self.sync, domain)
        dsync += If(emi_stb, emi_data_r.eq(emi_data))

        ps = PulseSynchronizer(domain, "sys")
        self.submodules += ps
        self.comb += ps.i.eq(emi_stb)
        self.sync += [
            If(rec_ack, rec_stb.eq(0)),
            If(ps.o,
                rec_data.eq(emi_data_r),
                rec_stb.eq(1)
            )
        ]


class RTPacketMaster(Module):
    def __init__(self, link_layer, write_fifo_depth=4):
        # all interface signals in sys domain unless otherwise specified

        # write interface, optimized for throughput
        self.write_stb = Signal()
        self.write_ack = Signal()
        self.write_timestamp = Signal(64)
        self.write_channel = Signal(16)
        self.write_address = Signal(16)
        self.write_data = Signal(512)

        # fifo space interface
        # write with timestamp[48:] == 0xffff to make a fifo space request
        # (space requests have to be ordered wrt writes)
        self.fifo_space_not = Signal()
        self.fifo_space_not_ack = Signal()
        self.fifo_space = Signal(16)

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

        # reset interface
        self.reset_stb = Signal()
        self.reset_ack = Signal()
        self.reset_phy = Signal()

        # errors
        self.error_not = Signal()
        self.error_not_ack = Signal()
        self.error_code = Signal(8)

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
        wfifo = ClockDomainsRenamer({"write": "sys_with_rst", "read": "rtio_with_rst"})(
            AsyncFIFO(64+16+16+512, write_fifo_depth))
        self.submodules += wfifo
        write_timestamp_d = Signal(64)
        write_channel_d = Signal(16)
        write_address_d = Signal(16)
        write_data_d = Signal(512)
        self.comb += [
            wfifo.we.eq(self.write_stb),
            self.write_ack.eq(wfifo.writable),
            wfifo.din.eq(Cat(self.write_timestamp, self.write_channel,
                             self.write_address, self.write_data)),
            Cat(write_timestamp_d, write_channel_d,
                write_address_d, write_data_d).eq(wfifo.dout)
        ]

        wfb_readable = Signal()
        wfb_re = Signal()

        self.comb += wfifo.re.eq(wfifo.readable & (~wfb_readable | wfb_re))
        self.sync.rtio += \
            If(wfifo.re,
                wfb_readable.eq(1),
            ).Elif(wfb_re,
                wfb_readable.eq(0),
            )

        write_timestamp = Signal(64)
        write_channel = Signal(16)
        write_address = Signal(16)
        write_extra_data_cnt = Signal(8)
        write_data = Signal(512)

        self.sync.rtio += If(wfifo.re,
            write_timestamp.eq(write_timestamp_d),
            write_channel.eq(write_channel_d),
            write_address.eq(write_address_d),
            write_data.eq(write_data_d))

        short_data_len = tx_plm.field_length("write", "short_data")
        write_extra_data_d = Signal(512)
        self.comb += write_extra_data_d.eq(write_data_d[short_data_len:])
        for i in range(512//ws):
            self.sync.rtio += If(wfifo.re,
                If(write_extra_data_d[ws*i:ws*(i+1)] != 0, write_extra_data_cnt.eq(i+1)))

        write_extra_data = Signal(512)
        self.sync.rtio += If(wfifo.re, write_extra_data.eq(write_extra_data_d))

        extra_data_ce = Signal()
        extra_data_last = Signal()
        extra_data_counter = Signal(max=512//ws+1)
        self.comb += [
            Case(extra_data_counter, 
                {i+1: tx_dp.raw_data.eq(write_extra_data[i*ws:(i+1)*ws])
                 for i in range(512//ws)}),
            extra_data_last.eq(extra_data_counter == write_extra_data_cnt)
        ]
        self.sync.rtio += \
            If(extra_data_ce,
                extra_data_counter.eq(extra_data_counter + 1),
            ).Else(
                extra_data_counter.eq(1)
            )

        # CDC
        fifo_space_not = Signal()
        fifo_space = Signal(16)
        self.submodules += _CrossDomainNotification("rtio_rx",
            fifo_space_not, fifo_space,
            self.fifo_space_not, self.fifo_space_not_ack, self.fifo_space)

        set_time_stb = Signal()
        set_time_ack = Signal()
        self.submodules += _CrossDomainRequest("rtio",
            self.set_time_stb, self.set_time_ack, None,
            set_time_stb, set_time_ack, None)

        reset_stb = Signal()
        reset_ack = Signal()
        reset_phy = Signal()
        self.submodules += _CrossDomainRequest("rtio",
            self.reset_stb, self.reset_ack, self.reset_phy,
            reset_stb, reset_ack, reset_phy)

        echo_stb = Signal()
        echo_ack = Signal()
        self.submodules += _CrossDomainRequest("rtio",
            self.echo_stb, self.echo_ack, None,
            echo_stb, echo_ack, None)

        error_not = Signal()
        error_code = Signal(8)
        self.submodules += _CrossDomainNotification("rtio_rx",
            error_not, error_code,
            self.error_not, self.error_not_ack, self.error_code)

        # TX FSM
        tx_fsm = ClockDomainsRenamer("rtio")(FSM(reset_state="IDLE"))
        self.submodules += tx_fsm

        echo_sent_now = Signal()
        self.sync.rtio += self.echo_sent_now.eq(echo_sent_now)
        tsc_value = Signal(64)
        tsc_value_load = Signal()
        self.sync.rtio += If(tsc_value_load, tsc_value.eq(self.tsc_value))

        tx_fsm.act("IDLE",
            If(wfb_readable,
                If(write_timestamp[48:] == 0xffff,
                    NextState("FIFO_SPACE")
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
                ).Elif(reset_stb,
                    NextState("RESET")
                )
            )
        )
        tx_fsm.act("WRITE",
            tx_dp.send("write",
                timestamp=write_timestamp,
                channel=write_channel,
                address=write_address,
                extra_data_cnt=write_extra_data_cnt,
                short_data=write_data[:short_data_len]),
            If(tx_dp.packet_last,
                If(write_extra_data_cnt == 0,
                    wfb_re.eq(1),
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
                wfb_re.eq(1),
                NextState("IDLE")
            )
        )
        tx_fsm.act("FIFO_SPACE",
            tx_dp.send("fifo_space_request", channel=write_channel),
            If(tx_dp.packet_last,
                wfb_re.eq(1),
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
        tx_fsm.act("RESET",
            tx_dp.send("reset", phy=reset_phy),
            If(tx_dp.packet_last,
                reset_ack.eq(1),
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
                        rx_plm.types["error"]: NextState("ERROR"),
                        rx_plm.types["echo_reply"]: echo_received_now.eq(1),
                        rx_plm.types["fifo_space_reply"]: NextState("FIFO_SPACE"),
                        "default": [
                            error_not.eq(1),
                            error_code.eq(error_codes["unknown_type_local"])
                        ]
                    })
                ).Else(
                    ongoing_packet_next.eq(1)
                )
            ),
            If(~rx_dp.frame_r & ongoing_packet,
                error_not.eq(1),
                error_code.eq(error_codes["truncated_local"])
            )
        )
        rx_fsm.act("ERROR",
            error_not.eq(1),
            error_code.eq(rx_dp.packet_as["error"].code),
            NextState("INPUT")
        )
        rx_fsm.act("FIFO_SPACE",
            fifo_space_not.eq(1),
            fifo_space.eq(rx_dp.packet_as["fifo_space_reply"].space),
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
