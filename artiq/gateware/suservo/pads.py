from migen import *
from migen.genlib.io import DifferentialOutput


class SamplerPads(Module):
    def __init__(self, platform, eem0, eem1):
        self.sck_p, self.sck_n = [
                platform.request("{}_adc_spi_{}".format(eem0, pol), 0).clk
                for pol in "pn"]
        pads = platform.request("{}_cnv".format(eem0), 0)
        self.cnv_b_p, self.cnv_b_n = pads.p, pads.n
        pads = platform.request("{}_sdr".format(eem0), 0)
        self.specials += DifferentialOutput(0, pads.p, pads.n)
        dp, dn = [
                platform.request("{}_adc_data_{}".format(eem0, pol), 0)
                for pol in "pn"]
        self.clkout_p, self.clkout_n = dp.clkout, dn.clkout
        self.sdoa_p, self.sdoa_n = dp.sdoa, dn.sdoa
        self.sdob_p, self.sdob_n = dp.sdob, dn.sdob
        self.sdoc_p, self.sdoc_n = dp.sdoc, dn.sdoc
        self.sdod_p, self.sdod_n = dp.sdod, dn.sdod


class UrukulPads(Module):
    def __init__(self, platform, eem00, eem01, eem10, eem11):
        spip, spin = [[
                platform.request("{}_qspi_{}".format(eem, pol), 0)
                for eem in (eem00, eem10)] for pol in "pn"]
        ioup = [platform.request("{}_io_update".format(eem), 0)
                for eem in (eem00, eem10)]
        self.cs_n = Signal()
        self.clk = Signal()
        self.io_update = Signal()
        self.specials += [(
                DifferentialOutput(self.cs_n, spip[i].cs_n, spin[i].cs_n),
                DifferentialOutput(self.clk, spip[i].clk, spin[i].clk),
                DifferentialOutput(self.io_update, ioup[i].p, ioup[i].n))
                for i in range(2)]
        for i in range(8):
            setattr(self, "mosi{}_p".format(i),
                    getattr(spip[i // 4], "mosi{}".format(i % 4)))
            setattr(self, "mosi{}_n".format(i),
                    getattr(spin[i // 4], "mosi{}".format(i % 4)))
