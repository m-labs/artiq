from functools import reduce
from operator import or_

from migen import *

from artiq.gateware.rtio.sed import layouts
from artiq.gateware.rtio.sed.output_network import OutputNetwork


__all__ = ["OutputDriver"]


class OutputDriver(Module):
    def __init__(self, channels, glbl_fine_ts_width, lane_count, seqn_width):
        self.collision = Signal()
        self.collision_channel = Signal(max=len(channels), reset_less=True)
        self.busy = Signal()
        self.busy_channel = Signal(max=len(channels), reset_less=True)

        # output network
        layout_on_payload = layouts.output_network_payload(channels, glbl_fine_ts_width)
        output_network = OutputNetwork(lane_count, seqn_width, layout_on_payload)
        self.submodules += output_network
        self.input = output_network.input

        # detect collisions (adds one pipeline stage)
        layout_lane_data = [
            ("valid", 1),
            ("collision", 1),
            ("payload", layout_on_payload)
        ]
        lane_datas = [Record(layout_lane_data, reset_less=True) for _ in range(lane_count)]
        en_replaces = [channel.interface.o.enable_replace for channel in channels]
        for lane_data, on_output in zip(lane_datas, output_network.output):
            lane_data.valid.reset_less = False
            lane_data.collision.reset_less = False
            replace_occured_r = Signal()
            nondata_replace_occured_r = Signal()
            self.sync += [
                lane_data.valid.eq(on_output.valid),
                lane_data.payload.eq(on_output.payload),
                replace_occured_r.eq(on_output.replace_occured),
                nondata_replace_occured_r.eq(on_output.nondata_replace_occured)
            ]

            en_replaces_rom = Memory(1, len(en_replaces), init=en_replaces)
            en_replaces_rom_port = en_replaces_rom.get_port()
            self.specials += en_replaces_rom, en_replaces_rom_port
            self.comb += [
                en_replaces_rom_port.adr.eq(on_output.payload.channel),
                lane_data.collision.eq(replace_occured_r & (~en_replaces_rom_port.dat_r | nondata_replace_occured_r))
            ]

        self.sync += [
            self.collision.eq(0),
            self.collision_channel.eq(0)
        ]
        for lane_data in lane_datas:
            self.sync += [
                If(lane_data.valid & lane_data.collision,
                    self.collision.eq(1),
                    self.collision_channel.eq(lane_data.payload.channel)
                )
            ]

        # demultiplex channels (adds one pipeline stage)
        for n, channel in enumerate(channels):
            oif = channel.interface.o

            onehot_stb = []
            onehot_fine_ts = []
            onehot_address = []
            onehot_data = []
            for lane_data in lane_datas:
                selected = Signal()
                self.comb += selected.eq(lane_data.valid & ~lane_data.collision & (lane_data.payload.channel == n))
                onehot_stb.append(selected)
                if hasattr(lane_data.payload, "fine_ts") and hasattr(oif, "fine_ts"):
                    ts_shift = len(lane_data.payload.fine_ts) - len(oif.fine_ts)
                    onehot_fine_ts.append(Mux(selected, lane_data.payload.fine_ts[ts_shift:], 0))
                if hasattr(lane_data.payload, "address"):
                    onehot_address.append(Mux(selected, lane_data.payload.address, 0))
                if hasattr(lane_data.payload, "data"):
                    onehot_data.append(Mux(selected, lane_data.payload.data, 0))

            self.sync += oif.stb.eq(reduce(or_, onehot_stb))
            if hasattr(oif, "fine_ts"):
                self.sync += oif.fine_ts.eq(reduce(or_, onehot_fine_ts))
            if hasattr(oif, "address"):
                self.sync += oif.address.eq(reduce(or_, onehot_address))
            if hasattr(oif, "data"):
                self.sync += oif.data.eq(reduce(or_, onehot_data))

        # detect busy errors, at lane level to reduce muxing
        self.sync += [
            self.busy.eq(0),
            self.busy_channel.eq(0)
        ]
        for lane_data in lane_datas:
            stb_r = Signal()
            channel_r = Signal(max=len(channels), reset_less=True)
            self.sync += [
                stb_r.eq(lane_data.valid & ~lane_data.collision),
                channel_r.eq(lane_data.payload.channel),

                If(stb_r & Array(channel.interface.o.busy for channel in channels)[channel_r],
                    self.busy.eq(1),
                    self.busy_channel.eq(channel_r)
                )
            ]
