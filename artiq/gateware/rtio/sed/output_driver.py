from functools import reduce
from operator import or_

from migen import *

from artiq.gateware.rtio import rtlink
from artiq.gateware.rtio.sed.output_network import OutputNetwork


class OutputDriver(Module):
    def __init__(self, channels, lane_count, seqn_width):
        self.collision = Signal()
        self.collision_channel = Signal(max=len(channels))
        self.busy = Signal()
        self.busy_channel = Signal(max=len(channels))

        fine_ts_width = max(rtlink.get_fine_ts_width(channel.interface)
                            for channel in channels)
        address_width = max(rtlink.get_address_width(channel.interface)
                            for channel in channels)
        data_width = max(rtlink.get_data_width(channel.interface)
                         for channel in channels)

        # output network
        layout_on_payload = [("channel", bits_for(len(channels)-1))]
        if fine_ts_width:
            layout_on_payload.append(("fine_ts", fine_ts_width))
        if address_width:
            layout_on_payload.append(("address", address_width))
        if data_width:
            layout_on_payload.append(("data", data_width))
        output_network = OutputNetwork(lane_count, seqn_width, layout_on_payload)
        self.submodules += output_network
        self.input = output_network.input

        # detect collisions (adds one pipeline stage)
        layout_lane_data = [
            ("valid", 1),
            ("collision", 1),
            ("payload", layout_on_payload)
        ]
        lane_datas = [Record(layout_lane_data) for _ in range(lane_count)]
        en_replaces = [channel.interface.o.enable_replace for channel in channels]
        for lane_data, on_output in zip(lane_datas, output_network.output):
            replace_occured_r = Signal()
            self.sync += [
                lane_data.valid.eq(on_output.valid),
                lane_data.payload.eq(on_output.payload),
                replace_occured_r.eq(on_output.replace_occured),
            ]

            en_replaces_rom = Memory(1, len(en_replaces), init=en_replaces)
            en_replaces_rom_port = en_replaces_rom.get_port()
            self.specials += en_replaces_rom, en_replaces_rom_port
            self.comb += [
                en_replaces_rom_port.adr.eq(on_output.payload.channel),
                lane_data.collision.eq(replace_occured_r & ~en_replaces_rom_port.dat_r)
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
            onehot_stb = []
            onehot_fine_ts = []
            onehot_address = []
            onehot_data = []
            for lane_data in lane_datas:
                selected = Signal()
                self.comb += selected.eq(lane_data.valid & ~lane_data.collision & (lane_data.payload.channel == n))
                onehot_stb.append(selected)
                if hasattr(lane_data.payload, "fine_ts"):
                    onehot_fine_ts.append(Mux(selected, lane_data.payload.fine_ts, 0))
                if hasattr(lane_data.payload, "address"):
                    onehot_address.append(Mux(selected, lane_data.payload.address, 0))
                if hasattr(lane_data.payload, "data"):
                    onehot_data.append(Mux(selected, lane_data.payload.data, 0))

            oif = channel.interface.o
            self.sync += oif.stb.eq(reduce(or_, onehot_stb))
            if hasattr(oif, "fine_ts"):
                self.sync += oif.fine_ts.eq(reduce(or_, onehot_fine_ts))
            if hasattr(oif, "address"):
                self.sync += oif.address.eq(reduce(or_, onehot_address))
            if hasattr(oif, "data"):
                self.sync += oif.data.eq(reduce(or_, onehot_data))

        # detect busy errors, at lane level to reduce muxing
        for lane_data in lane_datas:
            stb_r = Signal()
            channel_r = Signal(max=len(channels))
            self.sync += [
                stb_r.eq(lane_data.valid & ~lane_data.collision),
                channel_r.eq(lane_data.payload.channel),

                self.busy.eq(0),
                self.busy_channel.eq(0),
                If(stb_r & Array(channel.interface.o.busy for channel in channels)[channel_r],
                    self.busy.eq(1),
                    self.busy_channel.eq(channel_r)
                )
            ]
