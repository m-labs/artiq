from migen import *
from migen.genlib.record import Record
from migen.genlib.fifo import *
from migen.genlib.cdc import BlindTransfer

from artiq.gateware.rtio import cri
from artiq.gateware.rtio import rtlink


__all__ = ["InputCollector"]


def get_channel_layout(coarse_ts_width, interface):
    data_width = rtlink.get_data_width(interface)
    fine_ts_width = rtlink.get_fine_ts_width(interface)

    layout = []
    if data_width:
        layout.append(("data", data_width))
    if interface.timestamped:
        layout.append(("timestamp", coarse_ts_width + fine_ts_width))

    return layout


class InputCollector(Module):
    def __init__(self, tsc, channels, mode, quash_channels=[], interface=None):
        if interface is None:
            interface = cri.Interface()
        self.cri = interface

        # # #

        if mode == "sync":
            fifo_factory = SyncFIFOBuffered
            sync_io = self.sync
            sync_cri = self.sync
        elif mode == "async":
            fifo_factory = lambda *args: ClockDomainsRenamer({"write": "rio", "read": "rsys"})(AsyncFIFO(*args))
            sync_io = self.sync.rio
            sync_cri = self.sync.rsys
        else:
            raise ValueError

        i_statuses, i_datas, i_timestamps = [], [], []
        i_ack = Signal()
        sel = self.cri.chan_sel[:16]
        for n, channel in enumerate(channels):
            iif = channel.interface.i
            if iif is None or n in quash_channels:
                i_datas.append(0)
                i_timestamps.append(0)
                i_statuses.append(0)
                continue

            # FIFO
            layout = get_channel_layout(len(tsc.coarse_ts), iif)
            fifo = fifo_factory(layout_len(layout), channel.ififo_depth)
            self.submodules += fifo
            fifo_in = Record(layout)
            fifo_out = Record(layout)
            self.comb += [
                fifo.din.eq(fifo_in.raw_bits()),
                fifo_out.raw_bits().eq(fifo.dout)
            ]

            # FIFO write
            if iif.delay:
                counter_rtio = Signal.like(tsc.coarse_ts, reset_less=True)
                sync_io += counter_rtio.eq(tsc.coarse_ts - (iif.delay + 1))
            else:
                counter_rtio = tsc.coarse_ts
            if hasattr(fifo_in, "data"):
                self.comb += fifo_in.data.eq(iif.data)
            if hasattr(fifo_in, "timestamp"):
                if hasattr(iif, "fine_ts"):
                    full_ts = Cat(iif.fine_ts, counter_rtio)
                else:
                    full_ts = counter_rtio
                self.comb += fifo_in.timestamp.eq(full_ts)
            self.comb += fifo.we.eq(iif.stb)

            overflow_io = Signal()
            self.comb += overflow_io.eq(fifo.we & ~fifo.writable)
            if mode == "sync":
                overflow_trigger = overflow_io
            elif mode == "async":
                overflow_transfer = BlindTransfer("rio", "rsys")
                self.submodules += overflow_transfer
                self.comb += overflow_transfer.i.eq(overflow_io)
                overflow_trigger = overflow_transfer.o
            else:
                raise ValueError

            # FIFO read, CRI connection
            if hasattr(fifo_out, "data"):
                i_datas.append(fifo_out.data)
            else:
                i_datas.append(0)
            if hasattr(fifo_out, "timestamp"):
                ts_shift = 64 - len(fifo_out.timestamp)
                i_timestamps.append(fifo_out.timestamp << ts_shift)
            else:
                i_timestamps.append(0)

            selected = Signal()
            self.comb += selected.eq(sel == n)

            overflow = Signal()
            sync_cri += [
                If(selected & i_ack,
                    overflow.eq(0)),
                If(overflow_trigger,
                    overflow.eq(1))
            ]
            self.comb += fifo.re.eq(selected & i_ack & ~overflow)
            i_statuses.append(Cat(fifo.readable & ~overflow, overflow))

        i_status_raw = Signal(2)
        self.comb += i_status_raw.eq(Array(i_statuses)[sel])
        input_timeout = Signal.like(self.cri.i_timeout, reset_less=True)
        input_pending = Signal()
        self.cri.i_data.reset_less = True
        self.cri.i_timestamp.reset_less = True
        sync_cri += [
            i_ack.eq(0),
            If(i_ack,
                self.cri.i_status.eq(Cat(~i_status_raw[0], i_status_raw[1], 0)),
                self.cri.i_data.eq(Array(i_datas)[sel]),
                self.cri.i_timestamp.eq(Array(i_timestamps)[sel]),
            ),
            If((tsc.full_ts_cri >= input_timeout) | (i_status_raw != 0),
                If(input_pending, i_ack.eq(1)),
                input_pending.eq(0)
            ),
            If(self.cri.cmd == cri.commands["read"],
                input_timeout.eq(self.cri.i_timeout),
                input_pending.eq(1),
                self.cri.i_status.eq(0b100)
            )
        ]
