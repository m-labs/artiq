from migen import *
from migen.genlib.fsm import *

from artiq.gateware.rtio import cri
from artiq.gateware.drtio.rt_serializer import *


class RTPacketRepeater(Module):
    def __init__(self, link_layer):
        self.cri = cri.Interface()

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

        # Write buffer and extra data count
        wb_timestamp = Signal(64)
        wb_channel = Signal(16)
        wb_address = Signal(16)
        wb_data = Signal(512)
        self.sync.rtio += If(self.cri.cmd == cri.commands["write"],
            wb_timestamp.eq(self.cri.timestamp),
            wb_channel.eq(self.cri.chan_sel),
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

        # TX FSM
        tx_fsm = ClockDomainsRenamer("rtio")(FSM(reset_state="IDLE"))
        self.submodules += tx_fsm

        tx_fsm.act("IDLE",
            If(self.cri.cmd == cri.commands["write"], NextState("WRITE"))
        )
        tx_fsm.act("WRITE",
            tx_dp.send("write",
                timestamp=wb_timestamp,
                channel=wb_channel,
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
