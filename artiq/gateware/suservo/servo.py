from migen import *

from .adc_ser import ADC, ADCParams
from .iir import IIR, IIRWidths
from .dds_ser import DDS, DDSParams


class Servo(Module):
    def __init__(self, adc_pads, dds_pads, adc_p, iir_p, dds_p):
        self.submodules.adc = ADC(adc_pads, adc_p)
        self.submodules.iir = IIR(iir_p)
        self.submodules.dds = DDS(dds_pads, dds_p)

        # adc channels are reversed on Sampler
        for i, j, k, l in zip(reversed(self.adc.data), self.iir.adc,
                self.iir.dds, self.dds.profile):
            self.comb += j.eq(i), l.eq(k)

        t_adc = (adc_p.t_cnvh + adc_p.t_conv + adc_p.t_rtt +
            adc_p.channels*adc_p.width//adc_p.lanes) + 1
        t_iir = ((1 + 4 + 1) << iir_p.channel) + 1
        t_dds = (dds_p.width*2 + 1)*dds_p.clk + 1

        t_cycle = max(t_adc, t_iir, t_dds)
        assert t_iir + (2 << iir_p.channel) < t_cycle, "need shifting time"

        self.start = Signal()
        t_restart = t_cycle - t_adc + 1
        assert t_restart > 1
        cnt = Signal(max=t_restart)
        cnt_done = Signal()
        active = Signal(3)
        self.done = Signal()
        self.sync += [
                If(self.dds.done,
                    active[2].eq(0)
                ),
                If(self.dds.start & self.dds.done,
                    active[2].eq(1),
                    active[1].eq(0)
                ),
                If(self.iir.start & self.iir.done,
                    active[1].eq(1),
                    active[0].eq(0)
                ),
                If(~cnt_done & self.adc.done,
                    cnt.eq(cnt - 1)
                ),
                If(self.adc.start & self.adc.done,
                    active[0].eq(1),
                    cnt.eq(t_restart - 1)
                )
        ]
        self.comb += [
                cnt_done.eq(cnt == 0),
                self.adc.start.eq(self.start & cnt_done),
                self.iir.start.eq(active[0] & self.adc.done),
                self.dds.start.eq(active[1] &
                    (self.iir.shifting | self.iir.done)),
                self.done.eq(self.dds.done),
        ]
