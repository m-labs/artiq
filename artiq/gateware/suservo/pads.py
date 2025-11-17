from migen import *
from migen.genlib.io import DifferentialOutput, DifferentialInput, DDROutput
from artiq.gateware.rtio.phy import ttl_serdes_7series, ttl_serdes_generic
from artiq.gateware.rtio import rtlink


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


class OutIoUpdate_8X(Module):
    def __init__(self, pad):
        serdes = ttl_serdes_7series._OSERDESE2_8X()
        self.submodules += serdes

        # External trigger to issue pulses bypassing RTIO
        self.trigger = Signal()
        self.data = Signal()
        self.fine_ts = Signal(3)

        self.rtlink = rtlink.Interface(
            rtlink.OInterface(1, fine_ts_width=3))
        self.probes = []
        self.overrides = []

        # # #

        self.specials += Instance("IOBUFDS",
                                  i_I=serdes.ser_out,
                                  i_T=serdes.t_out,
                                  io_IO=pad.p,
                                  io_IOB=pad.n)

        trigger_r = Signal.like(self.trigger)
        extern_active = Signal()
        self.sync.rio_phy += trigger_r.eq(self.trigger)
        self.comb += extern_active.eq(self.trigger | trigger_r)

        self.submodules += ttl_serdes_generic._SerdesDriver(
            serdes.o,
            self.rtlink.o.stb | extern_active,
            Mux(extern_active, self.trigger, self.rtlink.o.data),
            Mux(extern_active, self.fine_ts, self.rtlink.o.fine_ts),
            0, 0)   # serdes override controls only supports coarse timestamp

        self.comb += self.rtlink.o.busy.eq(extern_active)


class UrukulPads(Module):
    def __init__(self, platform, io_update_fine_ts=False, *eems):
        spip, spin = [[
                platform.request("{}_qspi_{}".format(eem, pol), 0)
                for eem in eems] for pol in "pn"]
        ioup = [platform.request("{}_io_update".format(eem), 0)
                for eem in eems]
        self.clk = Signal()
        self.cs_n = Signal()
        self.io_update = Signal()
        if io_update_fine_ts:
            self.io_update_dlys = []
            self.ttl_rtio_phys = []

        for i in range(len(eems)):
            self.specials += DifferentialOutput(self.clk, spip[i].clk, spin[i].clk)
            if hasattr(spip[i], "cs"):
                self.specials += DifferentialOutput(~self.cs_n, spip[i].cs, spin[i].cs)
            if io_update_fine_ts:
                io_upd_phy = OutIoUpdate_8X(ioup[i])
                device_io_update_dly = Signal.like(io_upd_phy.fine_ts)
                self.comb += [
                    io_upd_phy.trigger.eq(self.io_update),
                    io_upd_phy.fine_ts.eq(device_io_update_dly),
                ]
                self.submodules += io_upd_phy
                self.io_update_dlys.append(device_io_update_dly)
                self.ttl_rtio_phys.append(io_upd_phy)
            else:
                self.specials += DifferentialOutput(self.io_update, ioup[i].p, ioup[i].n)

            for j in range(4):
                mosi = Signal()
                setattr(self, "mosi{}".format(i * 4 + j), mosi)
                self.specials += [
                    DifferentialOutput(getattr(self, "mosi{}".format(i * 4 + j)),
                        getattr(spip[i], "mosi{}".format(j)),
                        getattr(spin[i], "mosi{}".format(j)))
                ]
