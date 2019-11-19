from migen import *
from migen.genlib.io import DifferentialOutput, DifferentialInput, DDROutput


class SamplerPads(Module):
    def __init__(self, platform, eem):
        self.sck_en = Signal()
        self.cnv = Signal()
        self.clkout = Signal()

        spip = platform.request("{}_adc_spi_p".format(eem))
        spin = platform.request("{}_adc_spi_n".format(eem))
        cnv = platform.request("{}_cnv".format(eem))
        sdr = platform.request("{}_sdr".format(eem))
        dp = platform.request("{}_adc_data_p".format(eem))
        dn = platform.request("{}_adc_data_n".format(eem))

        clkout_se = Signal()
        clkout_inv = Signal()
        sck = Signal()

        self.specials += [
                DifferentialOutput(self.cnv, cnv.p, cnv.n),
                DifferentialOutput(1, sdr.p, sdr.n),
                DDROutput(self.sck_en, 0, sck, ClockSignal("rio_phy")),
                DifferentialOutput(sck, spip.clk, spin.clk),
                DifferentialInput(dp.clkout, dn.clkout, clkout_se),
                # FIXME (hardware): CLKOUT is inverted
                # (Sampler v2.0, v2.1) out on rising, in on falling
                Instance("BUFR", i_I=clkout_se, o_O=clkout_inv)
        ]
        self.comb += self.clkout.eq(~clkout_inv)

        # define clock here before the input delays below
        self.clkout_p = dp.clkout  # available for false paths
        platform.add_platform_command(
                "create_clock -name {clk} -period 8 [get_nets {clk}]",
                clk=dp.clkout)
        # platform.add_period_constraint(sampler_pads.clkout_p, 8.)
        for i in "abcd":
            sdo = Signal()
            setattr(self, "sdo{}".format(i), sdo)
            if i != "a":
                # FIXME (hardware): sdob, sdoc, sdod are inverted
                # (Sampler v2.0, v2.1)
                sdo, sdo_inv = Signal(), sdo
                self.comb += sdo_inv.eq(~sdo)
            sdop = getattr(dp, "sdo{}".format(i))
            sdon = getattr(dn, "sdo{}".format(i))
            self.specials += [
                DifferentialInput(sdop, sdon, sdo),
            ]
            # -0+1.5 hold (t_HSDO_SDR), -0.5+0.5 skew
            platform.add_platform_command(
                "set_input_delay -clock {clk} -max 2 [get_ports {port}]\n"
                "set_input_delay -clock {clk} -min -0.5 [get_ports {port}]",
                clk=dp.clkout, port=sdop)


class UrukulPads(Module):
    def __init__(self, platform, *eems):
        spip, spin = [[
                platform.request("{}_qspi_{}".format(eem, pol), 0)
                for eem in eems] for pol in "pn"]
        ioup = [platform.request("{}_io_update".format(eem), 0)
                for eem in eems]
        self.cs_n = Signal()
        self.clk = Signal()
        self.io_update = Signal()
        self.specials += [(
                DifferentialOutput(~self.cs_n, spip[i].cs, spin[i].cs),
                DifferentialOutput(self.clk, spip[i].clk, spin[i].clk),
                DifferentialOutput(self.io_update, ioup[i].p, ioup[i].n))
                for i in range(len(eems))]
        for i in range(8):
            mosi = Signal()
            setattr(self, "mosi{}".format(i), mosi)
        for i in range(4*len(eems)):
            self.specials += [
                DifferentialOutput(getattr(self, "mosi{}".format(i)),
                    getattr(spip[i // 4], "mosi{}".format(i % 4)),
                    getattr(spin[i // 4], "mosi{}".format(i % 4)))
            ]
