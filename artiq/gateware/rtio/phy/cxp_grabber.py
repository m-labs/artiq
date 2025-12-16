from migen import *
from migen.genlib.cdc import MultiReg 
from misoc.interconnect.csr import *
from misoc.cores.coaxpress.phy.high_speed_gtx import HostRXPHYs
from misoc.cores.coaxpress.phy.low_speed_serdes import HostTXPHYs
from misoc.cores.coaxpress.phy.asymmetric_gtx import HostTRXPHYs

from artiq.gateware.rtio import rtlink
from artiq.gateware.rtio.phy.grabber import Serializer, Synchronizer
from artiq.gateware.cxp_grabber.core import CXPHostCore, ROI, ROIViewer, StreamDecoder


class CXPGrabber(Module, AutoCSR):
    def __init__(
        self,
        refclk,
        gt_pads,
        sys_clk_freq,
        roi_engine_count=8,
        res_width=16,
        count_width=31,
        non_gt_tx_pads=None,
    ):
        assert count_width <= 31

        # Trigger rtio
        self.trigger = rtlink.Interface(rtlink.OInterface(3))

        
        # ROI rtio
         
        # 4 configs (x0, y0, x1, y1) per roi_engine
        self.config = rtlink.Interface(rtlink.OInterface(res_width, bits_for(4*roi_engine_count-1)))

        # select which roi engine can output rtio_input signal
        self.gate_data = rtlink.Interface(
            rtlink.OInterface(roi_engine_count),
            # the extra MSB bits is for sentinel
            rtlink.IInterface(count_width + 1, timestamped=False),
        )

        # # #

        if non_gt_tx_pads:
            self.submodules.phy_tx = tx = HostTXPHYs(non_gt_tx_pads, sys_clk_freq)
            self.submodules.phy_rx = rx = HostRXPHYs(refclk, gt_pads, sys_clk_freq)
            self.submodules.core = core = CXPHostCore(tx.phys[0], rx.phys[0], sys_clk_freq)
        else:
            self.submodules.phy = trx = HostTRXPHYs(refclk, gt_pads, sys_clk_freq)
            self.submodules.core = core = CXPHostCore(trx.phys[0], trx.phys[0], sys_clk_freq)

        self.sync.rio += [
            If(self.trigger.o.stb,
                Cat(core.tx.trig_extra_linktrig, core.tx.trig_linktrig_mode).eq(self.trigger.o.data),
            ),
            core.tx.trig_stb.eq(self.trigger.o.stb),
        ]

        self.submodules.stream_decoder = stream_decoder = StreamDecoder(res_width)
        self.comb += core.rx.source.connect(stream_decoder.sink)

        # ROI Viewer
        self.submodules.roi_viewer = ROIViewer(stream_decoder.source_pixel4x)

        # ROI engines configuration and count gating
        cdr = ClockDomainsRenamer("cxp_gt_rx")
        roi_engines = [
            cdr(ROI(stream_decoder.source_pixel4x, count_width))
            for _ in range(roi_engine_count)
        ]
        self.submodules += roi_engines

        for n, roi in enumerate(roi_engines):
            cfg = roi.cfg
            for offset, target in enumerate([cfg.x0, cfg.y0, cfg.x1, cfg.y1]):
                roi_boundary = Signal.like(target)
                self.sync.rio += If(self.config.o.stb & (self.config.o.address == 4*n+offset),
                                roi_boundary.eq(self.config.o.data))
                self.specials += MultiReg(roi_boundary, target, "cxp_gt_rx")

        self.submodules.synchronizer = synchronizer = ClockDomainsRenamer({"cl" : "cxp_gt_rx"})(Synchronizer(roi_engines))
        self.submodules.serializer = serializer = Serializer(synchronizer.update, synchronizer.counts, self.gate_data.i)
        
        self.sync.rio += If(self.gate_data.o.stb, serializer.gate.eq(self.gate_data.o.data))

