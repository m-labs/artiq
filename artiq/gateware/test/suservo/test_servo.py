import logging
import unittest
import numpy as np

from migen import *
from migen.genlib import io

from artiq.gateware.test.suservo import test_adc, test_dds
from artiq.gateware.suservo import servo

logger = logging.getLogger(__name__)


class ServoSim(servo.Servo):
    def __init__(self):
        adc_p = servo.ADCParams(width=16, channels=8, lanes=4,
                t_cnvh=4, t_conv=57 - 4, t_rtt=4 + 4)
        iir_p = servo.IIRWidths(state=25, coeff=18, adc=16, asf=14, word=16,
                accu=48, shift=11, profile=5, dly=8)
        dds_p = servo.DDSParams(width=8 + 32 + 16 + 16,
                channels=4, clk=1, sysclk_per_clk=8)

        self.submodules.adc_tb = test_adc.TB(adc_p)
        self.submodules.dds_tb = test_dds.TB(dds_p)

        servo.Servo.__init__(self, self.adc_tb, self.dds_tb,
                adc_p, iir_p, dds_p)

        self.dds_output = []

    def log_flow(self, cycle):
        su_start = yield self.start
        adc_start = yield self.adc.start
        iir_start = yield self.iir.start
        dds_start = yield self.dds.start
        su_done = yield self.done
        adc_done = yield self.adc.done
        iir_done = yield self.iir.done
        dds_done = yield self.dds.done
        active = yield self._active
        io_update = yield self.dds_tb.io_update
        passthrough = yield self.dds_tb.passthrough
        iir_loading = yield self.iir.loading
        iir_processing = yield self.iir.processing
        iir_shifting = yield self.iir.shifting
        dt = yield self.iir.t_running
        dt_iir = yield self.iir._dt_start
        state = yield self.iir._state
        stage0 = yield self.iir._stages[0]
        stage1 = yield self.iir._stages[1]
        stage2 = yield self.iir._stages[2]
        logger.debug(
            "cycle=%d "
            #"start=[su=%d adc=%d iir=%d dds=%d] "
            #"done=[su=%d adc=%d iir=%d dds=%d] "
            "active=%s load_proc_shft=%d%d%d stages_active=%d%d%d "
            "io_update=%d passthrough=%d "
            "dt=%d dt_iir=%d state=%d",
            cycle, 
            #su_start, adc_start, iir_start, dds_start,
            #su_done, adc_done, iir_done, dds_done, 
            '{:03b}'.format(active), iir_loading, iir_processing, iir_shifting, stage0, stage1, stage2,
            io_update, passthrough, 
            dt, dt_iir//8, state
        )

    def log_state(self, channel, profile, calls=[0]):
        calls[0] += 1
        # if not (yield self._active[1]):
        #     return
        yield from self.log_flow(calls[0] - 2)
        return
        cfg = yield from self.iir.get_coeff(channel, profile, "cfg")
        sel = cfg & 0x7
        x0 = yield from self.iir.get_state(sel, coeff="x0")
        x1 = yield from self.iir.get_state(sel, coeff="x1")
        y1 = yield from self.iir.get_state(channel, profile, coeff="y1")
        _pow = yield from self.iir.get_coeff(channel, profile, "pow")
        pow_iir = yield self.iir.dds[channel][2*self.iir.widths.word:3*self.iir.widths.word]
        pow_dds = yield self.dds_tb.ddss[channel].pow
        asf_dds = yield self.dds_tb.ddss[channel].asf
        ftw_dds = yield self.dds_tb.ddss[channel].ftw
        accu_dds = yield self.dds_tb.ddss[channel].accu
        phase_dds = (yield self.dds_tb.ddss[channel].phase)
        dds_output = np.cos(2*np.pi*phase_dds/2**19)
        ph_coh = yield self.iir._ph_coh
        ph_acc = yield self.iir._ph_acc
        offset = yield from self.iir.get_coeff(channel, profile, "offset")
        ftw0 = yield from self.iir.get_coeff(channel, profile, "ftw0")
        ftw1 = yield from self.iir.get_coeff(channel, profile, "ftw1")
        m_phase = yield from self.iir.get_accum_ftw(channel)
        iir_adc = yield self.iir.adc[sel]
        logger.debug("\t"
                     "ch=%d pr=%d "
                     # "x0=%d x1=%d adc=%d y1=%d sel=%d "
                     "ftw=%#x pow_coeff=%#x ftw_accu=%#x "
                     "ph_coh=%#x ph_acc=%#x "
                     "pow_iir=%#x pow_dds=%#x ftw_dds=%#x asf_dds=%#x accu_dds=%#x phase_dds=%#x dds_output=%04.3f",
                     channel, profile, 
                     # x0, x1, iir_adc, y1, sel,
                     ftw0 | (ftw1 << 16), _pow, m_phase,
                     ph_coh, ph_acc,  
                     pow_iir, pow_dds, ftw_dds, asf_dds, accu_dds, phase_dds >> 3, dds_output
        )
        self.dds_output.append(dds_output)
        # yield from self.log_registers(profile)

    def log_registers(self, profile):
        adc_channels = self.iir.widths_adc.channels
        dds_channels = self.iir.widths_dds.channels
        x0s = [0]*adc_channels
        x1s = [0]*adc_channels
        y1s = [0]*dds_channels
        for ch in range(adc_channels):
            x0s[ch] = yield from self.iir.get_state(ch, coeff="x0")
            x1s[ch] = yield from self.iir.get_state(ch, coeff="x1")
        for ch in range(dds_channels):
            y1s[ch] = yield from self.iir.get_state(ch, profile, coeff="y1")

        logger.debug(("x0s = " + '{:05X} ' * adc_channels).format(*x0s))
        logger.debug(("x1s = " + '{:05X} ' * adc_channels).format(*x1s))
        logger.debug(("y1s = " + '{:05X} ' * dds_channels).format(*y1s))

    def test(self):
        assert (yield self.done)

        adc = 7
        x0 = 0x0141
        yield self.adc_tb.data[-adc-1].eq(x0)
        channel = 0
        yield self.iir.ctrl[channel].en_iir.eq(1)
        yield self.iir.ctrl[channel].en_out.eq(1)
        yield self.iir.ctrl[channel].en_pt.eq(1)
        profile = 31
        yield self.iir.ctrl[channel].profile.eq(profile)
        x1 = 0x0743
        yield from self.iir.set_state(adc, x1, coeff="x1")
        y1 = 0x1145
        yield from self.iir.set_state(channel, y1,
                profile=profile, coeff="y1")
        coeff = dict(pow=0, offset=0x1531, ftw0=0xeb85, ftw1=0x51,
                a1=0x0135, b0=0x0337, b1=0x0539, cfg=adc)
        for ks in "pow offset ftw0 ftw1", "a1 b0 b1 cfg":
            for k in ks.split():
                yield from self.iir.set_coeff(channel, value=coeff[k],
                        profile=profile, coeff=k)
            yield

        num_it = 1
        num_proc_its = [0]*num_it # number of iterations while iir.processing
        yield from self.log_state(channel, profile)
        yield self.start.eq(1)
        yield
        for i in range(num_it):
            if i == 1:  # change ftw
                yield from self.iir.set_coeff(channel,
                    profile=profile, coeff='ftw0', value=coeff['ftw1'])
                yield from self.iir.set_coeff(channel,
                    profile=profile, coeff='ftw1', value=coeff['ftw0'])
            if i == 2:  # change ftw back
                yield from self.iir.set_coeff(channel,
                    profile=profile, coeff='ftw0', value=coeff['ftw0'])
                yield from self.iir.set_coeff(channel,
                    profile=profile, coeff='ftw1', value=coeff['ftw1'])
            logger.debug("iteration {}".format(i))
            yield from self.log_state(channel, profile)
            if i == num_it-1:
                yield self.start.eq(0)
            while not (yield self.dds_tb.io_update):
                yield
                if (yield self.iir.processing):
                    num_proc_its[i] += 1
                if (yield self.iir._stages) != 0:
                    yield from self.log_state(channel, profile)
            yield  # io_update
        yield from self.log_state(channel, profile)
        yield
        yield from self.log_state(channel, profile)

        np.savetxt('dds_output.dat', self.dds_output, fmt="%10.10f")
        logger.debug("number of iterations while iir.processing: {}".format(num_proc_its))
        w = self.iir.widths

        x0 = x0 << (w.state - w.adc - 1)
        _ = yield from self.iir.get_state(adc, coeff="x1")
        assert _ == x0, (hex(_), hex(x0))

        offset = coeff["offset"] << (w.state - w.coeff - 1)
        a1, b0, b1 = coeff["a1"], coeff["b0"], coeff["b1"]

        # works only for 1 iteration
        out = (
                0*(1 << w.shift - 1) +  # rounding
                a1*(y1 + 0) + b0*(x0 + offset) + b1*(x1 + offset)
        ) >> w.shift
        y1 = min(max(0, out), (1 << w.state - 1) - 1)

        _ = yield from self.iir.get_state(channel, profile, coeff="y1")
        assert _ == y1, (hex(_), hex(y1))

        _ = yield self.dds_tb.ddss[channel].ftw
        ftw = (coeff["ftw1"] << 16) | coeff["ftw0"]
        assert _ == ftw, (hex(_), hex(ftw))

        t0 = yield self.iir._dt_start
        # todo: include phase accumulator
        ph = (ftw * t0) >> 16
        if (yield self.iir.ctrl[channel].en_pt):
            pow = (coeff["pow"] + ph) & 0xffff
        else:
            pow = coeff["pow"]
        _ = yield self.dds_tb.ddss[channel].pow
        assert _ == pow, (hex(_), hex(pow))

        _ = yield self.dds_tb.ddss[channel].asf
        asf = y1 >> (w.state - w.asf - 1)
        assert _ == asf, (hex(_), hex(asf))


def main():
    servo = ServoSim()
    run_simulation(servo, servo.test(), vcd_name="servo.vcd",
            clocks={
                "sys":   (8, 0),
                "adc":   (8, 0),
                "ret":   (8, 0),
                "async": (2, 0),
            })


class ServoTest(unittest.TestCase):
    def test_run(self):
        main()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
