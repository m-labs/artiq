from migen import *

from .adc_ser import ADC, ADCParams
from .iir import IIR, IIRWidths
from .dds_ser import DDS, DDSParams


def predict_timing(adc_p, iir_p, dds_p):
    """
    The following is a sketch of the timing for 1 Sampler (8 ADCs) and N Urukuls
    Shown here, the cycle duration is limited by the IIR loading+processing time.

    ADC|CONVH|CONV|READ|RTT|IDLE|CONVH|CONV|READ|RTT|IDLE|CONVH|CONV|READ|RTT|...
       |4    |57  |16  |8  | .. |4    |57  |16  |8  | .. |4    |57  |16  |8  |...
    ---+-------------------+------------------------+------------------------+---
    IIR|                   |LOAD|PROC         |SHIFT|LOAD|PROC         |SHIFT|...
       |                   |8   |16*N+9       |16   |8   |16*N+9       |16   |...
    ---+--------------------------------------+------------------------+---------
    DDS|                                      |CMD|PROF|WAIT|IO_UP|IDLE|CMD|PR...
       |                                      |16 |128 |1   |1    | .. |16 |  ...

    IIR loading starts once the ADC presents its data, the DDSes are updated
    once the IIR processing is over. These are the only blocking processes.
    IIR shifting happens in parallel to writing to the DDSes and ADC conversions
    take place while the IIR filter is processing or the DDSes are being
    written to, depending on the cycle duration (given by whichever module
    takes the longest).
    """
    t_adc = (adc_p.t_cnvh + adc_p.t_conv + adc_p.t_rtt +
        adc_p.channels*adc_p.width//adc_p.lanes) + 1
    # load adc_p.channels values, process dds_p.channels
    # (4 processing phases and 2 additional stages à 4 phases
    # to complete the processing of the last channel)
    t_iir = adc_p.channels + 4*dds_p.channels + 8 + 1
    t_dds = (dds_p.width*2 + 1)*dds_p.clk + 1
    t_cycle = max(t_adc, t_iir, t_dds)
    return t_adc, t_iir, t_dds, t_cycle

class Servo(Module):
    def __init__(self, adc_pads, dds_pads, adc_p, iir_p, dds_p):
        t_adc, t_iir, t_dds, t_cycle = predict_timing(adc_p, iir_p, dds_p)
        assert t_iir + 2*adc_p.channels < t_cycle, "need shifting time"

        self.submodules.adc = ADC(adc_pads, adc_p)
        self.submodules.iir = IIR(iir_p)
        self.submodules.dds = DDS(dds_pads, dds_p)

        # adc channels are reversed on Sampler
        for iir, adc in zip(self.iir.adc, reversed(self.adc.data)):
            self.comb += iir.eq(adc)
        for dds, iir in zip(self.dds.profile, self.iir.dds):
            self.comb += dds.eq(iir)

        # If high, a new cycle is started if the current cycle (if any) is
        # finished. Consequently, if low, servo iterations cease after the
        # current cycle is finished. Don't care while the first step (ADC)
        # is active.
        self.start = Signal()

        # Counter for delay between end of ADC cycle and start of next one,
        # depending on the duration of the other steps.
        t_restart = t_cycle - t_adc + 1
        assert t_restart > 1
        cnt = Signal(max=t_restart)
        cnt_done = Signal()
        active = Signal(3)

        # Indicates whether different steps (0: ADC, 1: IIR, 2: DDS) are
        # currently active (exposed for simulation only), with each bit being
        # reset once the successor step is launched. Depending on the
        # timing details of the different steps, any number can be concurrently
        # active (e.g. ADC read from iteration n, IIR computation from iteration
        # n - 1, and DDS write from iteration n - 2).

        # Asserted once per cycle when the DDS write has been completed.
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
