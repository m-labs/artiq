from migen import *
from migen.build.generic_platform import *
from migen.genlib.io import DifferentialOutput

from artiq.gateware import rtio
from artiq.gateware.rtio.phy import spi2, ad53xx_monitor, grabber
from artiq.gateware.suservo import servo, pads as servo_pads
from artiq.gateware.rtio.phy import servo as rtservo, fastino


def _eem_signal(i):
    n = "d{}".format(i)
    if i == 0:
        n += "_cc"
    return n


def _eem_pin(eem, i, pol):
    return "eem{}:{}_{}".format(eem, _eem_signal(i), pol)


class _EEM:
    @classmethod
    def add_extension(cls, target, eem, *args, **kwargs):
        name = cls.__name__
        target.platform.add_extension(cls.io(eem, *args, **kwargs))
        print("{} (EEM{}) starting at RTIO channel 0x{:06x}"
              .format(name, eem, len(target.rtio_channels)))


class DIO(_EEM):
    @staticmethod
    def io(eem, iostandard="LVDS_25"):
        return [("dio{}".format(eem), i,
            Subsignal("p", Pins(_eem_pin(eem, i, "p"))),
            Subsignal("n", Pins(_eem_pin(eem, i, "n"))),
            IOStandard(iostandard))
            for i in range(8)]

    @classmethod
    def add_std(cls, target, eem, ttl03_cls, ttl47_cls, iostandard="LVDS_25",
            edge_counter_cls=None):
        cls.add_extension(target, eem, iostandard=iostandard)

        phys = []
        for i in range(4):
            pads = target.platform.request("dio{}".format(eem), i)
            phy = ttl03_cls(pads.p, pads.n)
            phys.append(phy)
            target.submodules += phy
            target.rtio_channels.append(rtio.Channel.from_phy(phy))
        for i in range(4):
            pads = target.platform.request("dio{}".format(eem), 4+i)
            phy = ttl47_cls(pads.p, pads.n)
            phys.append(phy)
            target.submodules += phy
            target.rtio_channels.append(rtio.Channel.from_phy(phy))

        if edge_counter_cls is not None:
            for phy in phys:
                state = getattr(phy, "input_state", None)
                if state is not None:
                    counter = edge_counter_cls(state)
                    target.submodules += counter
                    target.rtio_channels.append(rtio.Channel.from_phy(counter))


class Urukul(_EEM):
    @staticmethod
    def io(eem, eem_aux, iostandard="LVDS_25"):
        ios = [
            ("urukul{}_spi_p".format(eem), 0,
                Subsignal("clk", Pins(_eem_pin(eem, 0, "p"))),
                Subsignal("mosi", Pins(_eem_pin(eem, 1, "p"))),
                Subsignal("miso", Pins(_eem_pin(eem, 2, "p"))),
                Subsignal("cs_n", Pins(
                    *(_eem_pin(eem, i + 3, "p") for i in range(3)))),
                IOStandard(iostandard),
            ),
            ("urukul{}_spi_n".format(eem), 0,
                Subsignal("clk", Pins(_eem_pin(eem, 0, "n"))),
                Subsignal("mosi", Pins(_eem_pin(eem, 1, "n"))),
                Subsignal("miso", Pins(_eem_pin(eem, 2, "n"))),
                Subsignal("cs_n", Pins(
                    *(_eem_pin(eem, i + 3, "n") for i in range(3)))),
                IOStandard(iostandard),
            ),
        ]
        ttls = [(6, eem, "io_update"),
                (7, eem, "dds_reset_sync_in", Misc("IOB=TRUE"))]
        if eem_aux is not None:
            ttls += [(0, eem_aux, "sync_clk"),
                     (1, eem_aux, "sync_in"),
                     (2, eem_aux, "io_update_ret"),
                     (3, eem_aux, "nu_mosi3"),
                     (4, eem_aux, "sw0"),
                     (5, eem_aux, "sw1"),
                     (6, eem_aux, "sw2"),
                     (7, eem_aux, "sw3")]
        for i, j, sig, *extra_args in ttls:
            ios.append(
                ("urukul{}_{}".format(eem, sig), 0,
                    Subsignal("p", Pins(_eem_pin(j, i, "p"))),
                    Subsignal("n", Pins(_eem_pin(j, i, "n"))),
                    IOStandard(iostandard), *extra_args
                ))
        return ios

    @staticmethod
    def io_qspi(eem0, eem1, iostandard="LVDS_25"):
        ios = [
            ("urukul{}_spi_p".format(eem0), 0,
                Subsignal("clk", Pins(_eem_pin(eem0, 0, "p"))),
                Subsignal("mosi", Pins(_eem_pin(eem0, 1, "p"))),
                Subsignal("cs_n", Pins(
                    _eem_pin(eem0, 3, "p"), _eem_pin(eem0, 4, "p"))),
                IOStandard(iostandard),
            ),
            ("urukul{}_spi_n".format(eem0), 0,
                Subsignal("clk", Pins(_eem_pin(eem0, 0, "n"))),
                Subsignal("mosi", Pins(_eem_pin(eem0, 1, "n"))),
                Subsignal("cs_n", Pins(
                    _eem_pin(eem0, 3, "n"), _eem_pin(eem0, 4, "n"))),
                IOStandard(iostandard),
            ),
        ]
        ttls = [(6, eem0, "io_update"),
                (7, eem0, "dds_reset_sync_in"),
                (4, eem1, "sw0"),
                (5, eem1, "sw1"),
                (6, eem1, "sw2"),
                (7, eem1, "sw3")]
        for i, j, sig in ttls:
            ios.append(
                ("urukul{}_{}".format(eem0, sig), 0,
                    Subsignal("p", Pins(_eem_pin(j, i, "p"))),
                    Subsignal("n", Pins(_eem_pin(j, i, "n"))),
                    IOStandard(iostandard)
                ))
        ios += [
            ("urukul{}_qspi_p".format(eem0), 0,
                Subsignal("cs", Pins(_eem_pin(eem0, 5, "p"))),
                Subsignal("clk", Pins(_eem_pin(eem0, 2, "p"))),
                Subsignal("mosi0", Pins(_eem_pin(eem1, 0, "p"))),
                Subsignal("mosi1", Pins(_eem_pin(eem1, 1, "p"))),
                Subsignal("mosi2", Pins(_eem_pin(eem1, 2, "p"))),
                Subsignal("mosi3", Pins(_eem_pin(eem1, 3, "p"))),
                IOStandard(iostandard),
            ),
            ("urukul{}_qspi_n".format(eem0), 0,
                Subsignal("cs", Pins(_eem_pin(eem0, 5, "n"))),
                Subsignal("clk", Pins(_eem_pin(eem0, 2, "n"))),
                Subsignal("mosi0", Pins(_eem_pin(eem1, 0, "n"))),
                Subsignal("mosi1", Pins(_eem_pin(eem1, 1, "n"))),
                Subsignal("mosi2", Pins(_eem_pin(eem1, 2, "n"))),
                Subsignal("mosi3", Pins(_eem_pin(eem1, 3, "n"))),
                IOStandard(iostandard),
            ),
        ]
        return ios

    @classmethod
    def add_std(cls, target, eem, eem_aux, ttl_out_cls, sync_gen_cls=None,
                iostandard="LVDS_25"):
        cls.add_extension(target, eem, eem_aux, iostandard=iostandard)

        phy = spi2.SPIMaster(target.platform.request("urukul{}_spi_p".format(eem)),
            target.platform.request("urukul{}_spi_n".format(eem)))
        target.submodules += phy
        target.rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=4))

        pads = target.platform.request("urukul{}_dds_reset_sync_in".format(eem))
        pad = Signal(reset=0)
        target.specials += DifferentialOutput(pad, pads.p, pads.n)
        if sync_gen_cls is not None:  # AD9910 variant and SYNC_IN from EEM
            phy = sync_gen_cls(pad, ftw_width=4)
            target.submodules += phy
            target.rtio_channels.append(rtio.Channel.from_phy(phy))

        pads = target.platform.request("urukul{}_io_update".format(eem))
        phy = ttl_out_cls(pads.p, pads.n)
        target.submodules += phy
        target.rtio_channels.append(rtio.Channel.from_phy(phy))
        if eem_aux is not None:
            for signal in "sw0 sw1 sw2 sw3".split():
                pads = target.platform.request("urukul{}_{}".format(eem, signal))
                phy = ttl_out_cls(pads.p, pads.n)
                target.submodules += phy
                target.rtio_channels.append(rtio.Channel.from_phy(phy))

class Sampler(_EEM):
    @staticmethod
    def io(eem, eem_aux, iostandard="LVDS_25"):
        ios = [
            ("sampler{}_adc_spi_p".format(eem), 0,
                Subsignal("clk", Pins(_eem_pin(eem, 0, "p"))),
                Subsignal("miso", Pins(_eem_pin(eem, 1, "p"))),
                IOStandard(iostandard),
            ),
            ("sampler{}_adc_spi_n".format(eem), 0,
                Subsignal("clk", Pins(_eem_pin(eem, 0, "n"))),
                Subsignal("miso", Pins(_eem_pin(eem, 1, "n"))),
                IOStandard(iostandard),
            ),
            ("sampler{}_pgia_spi_p".format(eem), 0,
                Subsignal("clk", Pins(_eem_pin(eem, 4, "p"))),
                Subsignal("mosi", Pins(_eem_pin(eem, 5, "p"))),
                Subsignal("miso", Pins(_eem_pin(eem, 6, "p"))),
                Subsignal("cs_n", Pins(_eem_pin(eem, 7, "p"))),
                IOStandard(iostandard),
            ),
            ("sampler{}_pgia_spi_n".format(eem), 0,
                Subsignal("clk", Pins(_eem_pin(eem, 4, "n"))),
                Subsignal("mosi", Pins(_eem_pin(eem, 5, "n"))),
                Subsignal("miso", Pins(_eem_pin(eem, 6, "n"))),
                Subsignal("cs_n", Pins(_eem_pin(eem, 7, "n"))),
                IOStandard(iostandard),
            ),
        ] + [
            ("sampler{}_{}".format(eem, sig), 0,
                Subsignal("p", Pins(_eem_pin(j, i, "p"))),
                Subsignal("n", Pins(_eem_pin(j, i, "n"))),
                IOStandard(iostandard)
            ) for i, j, sig in [
                (2, eem, "sdr"),
                (3, eem, "cnv")
            ]
        ]
        if eem_aux is not None:
            ios += [
                ("sampler{}_adc_data_p".format(eem), 0,
                    Subsignal("clkout", Pins(_eem_pin(eem_aux, 0, "p"))),
                    Subsignal("sdoa", Pins(_eem_pin(eem_aux, 1, "p"))),
                    Subsignal("sdob", Pins(_eem_pin(eem_aux, 2, "p"))),
                    Subsignal("sdoc", Pins(_eem_pin(eem_aux, 3, "p"))),
                    Subsignal("sdod", Pins(_eem_pin(eem_aux, 4, "p"))),
                    Misc("DIFF_TERM=TRUE"),
                    IOStandard(iostandard),
                ),
                ("sampler{}_adc_data_n".format(eem), 0,
                    Subsignal("clkout", Pins(_eem_pin(eem_aux, 0, "n"))),
                    Subsignal("sdoa", Pins(_eem_pin(eem_aux, 1, "n"))),
                    Subsignal("sdob", Pins(_eem_pin(eem_aux, 2, "n"))),
                    Subsignal("sdoc", Pins(_eem_pin(eem_aux, 3, "n"))),
                    Subsignal("sdod", Pins(_eem_pin(eem_aux, 4, "n"))),
                    Misc("DIFF_TERM=TRUE"),
                    IOStandard(iostandard),
                ),
            ]
        return ios

    @classmethod
    def add_std(cls, target, eem, eem_aux, ttl_out_cls, iostandard="LVDS_25"):
        cls.add_extension(target, eem, eem_aux, iostandard=iostandard)

        phy = spi2.SPIMaster(
                target.platform.request("sampler{}_adc_spi_p".format(eem)),
                target.platform.request("sampler{}_adc_spi_n".format(eem)))
        target.submodules += phy
        target.rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=4))
        phy = spi2.SPIMaster(
                target.platform.request("sampler{}_pgia_spi_p".format(eem)),
                target.platform.request("sampler{}_pgia_spi_n".format(eem)))
        target.submodules += phy

        target.rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=4))
        pads = target.platform.request("sampler{}_cnv".format(eem))
        phy = ttl_out_cls(pads.p, pads.n)
        target.submodules += phy

        target.rtio_channels.append(rtio.Channel.from_phy(phy))
        sdr = target.platform.request("sampler{}_sdr".format(eem))
        target.specials += DifferentialOutput(1, sdr.p, sdr.n)


class Novogorny(_EEM):
    @staticmethod
    def io(eem, iostandard="LVDS_25"):
        return [
            ("novogorny{}_spi_p".format(eem), 0,
                Subsignal("clk", Pins(_eem_pin(eem, 0, "p"))),
                Subsignal("mosi", Pins(_eem_pin(eem, 1, "p"))),
                Subsignal("miso", Pins(_eem_pin(eem, 2, "p"))),
                Subsignal("cs_n", Pins(
                    _eem_pin(eem, 3, "p"), _eem_pin(eem, 4, "p"))),
                IOStandard(iostandard),
            ),
            ("novogorny{}_spi_n".format(eem), 0,
                Subsignal("clk", Pins(_eem_pin(eem, 0, "n"))),
                Subsignal("mosi", Pins(_eem_pin(eem, 1, "n"))),
                Subsignal("miso", Pins(_eem_pin(eem, 2, "n"))),
                Subsignal("cs_n", Pins(
                    _eem_pin(eem, 3, "n"), _eem_pin(eem, 4, "n"))),
                IOStandard(iostandard),
            ),
        ] + [
            ("novogorny{}_{}".format(eem, sig), 0,
                Subsignal("p", Pins(_eem_pin(j, i, "p"))),
                Subsignal("n", Pins(_eem_pin(j, i, "n"))),
                IOStandard(iostandard)
            ) for i, j, sig in [
                (5, eem, "cnv"),
                (6, eem, "busy"),
                (7, eem, "scko"),
            ]
        ]

    @classmethod
    def add_std(cls, target, eem, ttl_out_cls, iostandard="LVDS_25"):
        cls.add_extension(target, eem, iostandard=iostandard)

        phy = spi2.SPIMaster(target.platform.request("novogorny{}_spi_p".format(eem)),
                target.platform.request("novogorny{}_spi_n".format(eem)))
        target.submodules += phy
        target.rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=16))

        pads = target.platform.request("novogorny{}_cnv".format(eem))
        phy = ttl_out_cls(pads.p, pads.n)
        target.submodules += phy
        target.rtio_channels.append(rtio.Channel.from_phy(phy))


class Zotino(_EEM):
    @staticmethod
    def io(eem, iostandard="LVDS_25"):
        return [
            ("zotino{}_spi_p".format(eem), 0,
                Subsignal("clk", Pins(_eem_pin(eem, 0, "p"))),
                Subsignal("mosi", Pins(_eem_pin(eem, 1, "p"))),
                Subsignal("miso", Pins(_eem_pin(eem, 2, "p"))),
                Subsignal("cs_n", Pins(
                    _eem_pin(eem, 3, "p"), _eem_pin(eem, 4, "p"))),
                IOStandard(iostandard),
            ),
            ("zotino{}_spi_n".format(eem), 0,
                Subsignal("clk", Pins(_eem_pin(eem, 0, "n"))),
                Subsignal("mosi", Pins(_eem_pin(eem, 1, "n"))),
                Subsignal("miso", Pins(_eem_pin(eem, 2, "n"))),
                Subsignal("cs_n", Pins(
                    _eem_pin(eem, 3, "n"), _eem_pin(eem, 4, "n"))),
                IOStandard(iostandard),
            ),
        ] + [
            ("zotino{}_{}".format(eem, sig), 0,
                    Subsignal("p", Pins(_eem_pin(j, i, "p"))),
                    Subsignal("n", Pins(_eem_pin(j, i, "n"))),
                    IOStandard(iostandard)
            ) for i, j, sig in [
                (5, eem, "ldac_n"),
                (6, eem, "busy"),
                (7, eem, "clr_n"),
            ]
        ]

    @classmethod
    def add_std(cls, target, eem, ttl_out_cls, iostandard="LVDS_25"):
        cls.add_extension(target, eem, iostandard=iostandard)

        spi_phy = spi2.SPIMaster(target.platform.request("zotino{}_spi_p".format(eem)),
            target.platform.request("zotino{}_spi_n".format(eem)))
        target.submodules += spi_phy
        target.rtio_channels.append(rtio.Channel.from_phy(spi_phy, ififo_depth=4))

        pads = target.platform.request("zotino{}_ldac_n".format(eem))
        ldac_phy = ttl_out_cls(pads.p, pads.n)
        target.submodules += ldac_phy
        target.rtio_channels.append(rtio.Channel.from_phy(ldac_phy))

        pads = target.platform.request("zotino{}_clr_n".format(eem))
        clr_phy = ttl_out_cls(pads.p, pads.n)
        target.submodules += clr_phy
        target.rtio_channels.append(rtio.Channel.from_phy(clr_phy))

        dac_monitor = ad53xx_monitor.AD53XXMonitor(spi_phy.rtlink, ldac_phy.rtlink)
        target.submodules += dac_monitor
        spi_phy.probes.extend(dac_monitor.probes)


class Grabber(_EEM):
    @staticmethod
    def io(eem, eem_aux, iostandard="LVDS_25"):
        ios = [
            ("grabber{}_video".format(eem), 0,
                Subsignal("clk_p", Pins(_eem_pin(eem, 0, "p"))),
                Subsignal("clk_n", Pins(_eem_pin(eem, 0, "n"))),
                Subsignal("sdi_p", Pins(*[_eem_pin(eem, i, "p") for i in range(1, 5)])),
                Subsignal("sdi_n", Pins(*[_eem_pin(eem, i, "n") for i in range(1, 5)])),
                IOStandard(iostandard), Misc("DIFF_TERM=TRUE")
            ),
            ("grabber{}_cc0".format(eem), 0,
                Subsignal("p", Pins(_eem_pin(eem_aux, 5, "p"))),
                Subsignal("n", Pins(_eem_pin(eem_aux, 5, "n"))),
                IOStandard(iostandard)
            ),
            ("grabber{}_cc1".format(eem), 0,
                Subsignal("p", Pins(_eem_pin(eem_aux, 6, "p"))),
                Subsignal("n", Pins(_eem_pin(eem_aux, 6, "n"))),
                IOStandard(iostandard)
            ),
            ("grabber{}_cc2".format(eem), 0,
                Subsignal("p", Pins(_eem_pin(eem_aux, 7, "p"))),
                Subsignal("n", Pins(_eem_pin(eem_aux, 7, "n"))),
                IOStandard(iostandard)
            ),
        ]
        if eem_aux is not None:
            ios += [
                ("grabber{}_video_m".format(eem), 0,
                    Subsignal("clk_p", Pins(_eem_pin(eem_aux, 0, "p"))),
                    Subsignal("clk_n", Pins(_eem_pin(eem_aux, 0, "n"))),
                    Subsignal("sdi_p", Pins(*[_eem_pin(eem_aux, i, "p") for i in range(1, 5)])),
                    Subsignal("sdi_n", Pins(*[_eem_pin(eem_aux, i, "n") for i in range(1, 5)])),
                    IOStandard(iostandard), Misc("DIFF_TERM=TRUE")
                ),
                ("grabber{}_serrx".format(eem), 0,
                    Subsignal("p", Pins(_eem_pin(eem_aux, 5, "p"))),
                    Subsignal("n", Pins(_eem_pin(eem_aux, 5, "n"))),
                    IOStandard(iostandard), Misc("DIFF_TERM=TRUE")
                ),
                ("grabber{}_sertx".format(eem), 0,
                    Subsignal("p", Pins(_eem_pin(eem_aux, 6, "p"))),
                    Subsignal("n", Pins(_eem_pin(eem_aux, 6, "n"))),
                    IOStandard(iostandard)
                ),
                ("grabber{}_cc3".format(eem), 0,
                    Subsignal("p", Pins(_eem_pin(eem_aux, 7, "p"))),
                    Subsignal("n", Pins(_eem_pin(eem_aux, 7, "n"))),
                    IOStandard(iostandard)
                ),
            ]
        return ios

    @classmethod
    def add_std(cls, target, eem, eem_aux=None, eem_aux2=None, ttl_out_cls=None, iostandard="LVDS_25"):
        cls.add_extension(target, eem, eem_aux, iostandard=iostandard)

        pads = target.platform.request("grabber{}_video".format(eem))
        target.platform.add_period_constraint(pads.clk_p, 14.71)
        phy = grabber.Grabber(pads)
        name = "grabber{}".format(len(target.grabber_csr_group))
        setattr(target.submodules, name, phy)

        target.platform.add_false_path_constraints(
            target.crg.cd_sys.clk, phy.deserializer.cd_cl.clk)
        # Avoid bogus s/h violations at the clock input being sampled
        # by the ISERDES. This uses dynamic calibration.
        target.platform.add_false_path_constraints(
            pads.clk_p, phy.deserializer.cd_cl7x.clk)

        target.grabber_csr_group.append(name)
        target.csr_devices.append(name)
        target.rtio_channels += [
            rtio.Channel(phy.config),
            rtio.Channel(phy.gate_data)
        ]

        if ttl_out_cls is not None:
            for signal in "cc0 cc1 cc2".split():
                pads = target.platform.request("grabber{}_{}".format(eem, signal))
                phy = ttl_out_cls(pads.p, pads.n)
                target.submodules += phy
                target.rtio_channels.append(rtio.Channel.from_phy(phy))
            if eem_aux is not None:
                pads = target.platform.request("grabber{}_cc3".format(eem))
                phy = ttl_out_cls(pads.p, pads.n)
                target.submodules += phy
                target.rtio_channels.append(rtio.Channel.from_phy(phy))


class SUServo(_EEM):
    @staticmethod
    def io(*eems, iostandard="LVDS_25"):
        assert len(eems) in (4, 6)
        io = (Sampler.io(*eems[0:2], iostandard=iostandard)
                + Urukul.io_qspi(*eems[2:4], iostandard=iostandard))
        if len(eems) == 6:  # two Urukuls
            io += Urukul.io_qspi(*eems[4:6], iostandard=iostandard)
        return io

    @classmethod
    def add_std(cls, target, eems_sampler, eems_urukul,
                t_rtt=4, clk=1, shift=11, profile=5,
                iostandard="LVDS_25"):
        """Add a 8-channel Sampler-Urukul Servo

        :param t_rtt: upper estimate for clock round-trip propagation time from
            ``sck`` at the FPGA to ``clkout`` at the FPGA, measured in RTIO
            coarse cycles (default: 4). This is the sum of the round-trip
            cabling delay and the 8 ns max propagation delay on Sampler (ADC
            and LVDS drivers). Increasing ``t_rtt`` increases servo latency.
            With all other parameters at their default values, ``t_rtt`` values
            above 4 also increase the servo period (reduce servo bandwidth).
        :param clk: DDS SPI clock cycle half-width in RTIO coarse cycles
            (default: 1)
        :param shift: fixed-point scaling factor for IIR coefficients
            (default: 11)
        :param profile: log2 of the number of profiles for each DDS channel
            (default: 5)
        """
        cls.add_extension(
            target, *(eems_sampler + sum(eems_urukul, [])),
            iostandard=iostandard)
        eem_sampler = "sampler{}".format(eems_sampler[0])
        eem_urukul = ["urukul{}".format(i[0]) for i in eems_urukul]

        sampler_pads = servo_pads.SamplerPads(target.platform, eem_sampler)
        urukul_pads = servo_pads.UrukulPads(
            target.platform, *eem_urukul)
        target.submodules += sampler_pads, urukul_pads
        # timings in units of RTIO coarse period
        adc_p = servo.ADCParams(width=16, channels=8, lanes=4, t_cnvh=4,
                                # account for SCK DDR to CONV latency
                                # difference (4 cycles measured)
                                t_conv=57 - 4, t_rtt=t_rtt + 4)
        iir_p = servo.IIRWidths(state=25, coeff=18, adc=16, asf=14, word=16,
                                accu=48, shift=shift, channel=3,
                                profile=profile, dly=8)
        dds_p = servo.DDSParams(width=8 + 32 + 16 + 16,
                                channels=adc_p.channels, clk=clk)
        su = servo.Servo(sampler_pads, urukul_pads, adc_p, iir_p, dds_p)
        su = ClockDomainsRenamer("rio_phy")(su)
        # explicitly name the servo submodule to enable the migen namer to derive
        # a name for the adc return clock domain
        setattr(target.submodules, "suservo_eem{}".format(eems_sampler[0]), su)

        ctrls = [rtservo.RTServoCtrl(ctrl) for ctrl in su.iir.ctrl]
        target.submodules += ctrls
        target.rtio_channels.extend(
            rtio.Channel.from_phy(ctrl) for ctrl in ctrls)
        mem = rtservo.RTServoMem(iir_p, su)
        target.submodules += mem
        target.rtio_channels.append(rtio.Channel.from_phy(mem, ififo_depth=4))

        phy = spi2.SPIMaster(
            target.platform.request("{}_pgia_spi_p".format(eem_sampler)),
            target.platform.request("{}_pgia_spi_n".format(eem_sampler)))
        target.submodules += phy
        target.rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=4))

        for i in range(2):
            if len(eem_urukul) > i:
                spi_p, spi_n = (
                    target.platform.request("{}_spi_p".format(eem_urukul[i])),
                    target.platform.request("{}_spi_n".format(eem_urukul[i])))
            else:  # create a dummy bus
                spi_p = Record([("clk", 1), ("cs_n", 1)])  # mosi, cs_n
                spi_n = None

            phy = spi2.SPIMaster(spi_p, spi_n)
            target.submodules += phy
            target.rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=4))

        for j, eem_urukuli in enumerate(eem_urukul):
            pads = target.platform.request("{}_dds_reset_sync_in".format(eem_urukuli))
            target.specials += DifferentialOutput(0, pads.p, pads.n)

            for i, signal in enumerate("sw0 sw1 sw2 sw3".split()):
                pads = target.platform.request("{}_{}".format(eem_urukuli, signal))
                target.specials += DifferentialOutput(
                    su.iir.ctrl[j*4 + i].en_out, pads.p, pads.n)


class Mirny(_EEM):
    @staticmethod
    def io(eem, iostandard="LVDS_25"):
        ios = [
            ("mirny{}_spi_p".format(eem), 0,
                Subsignal("clk", Pins(_eem_pin(eem, 0, "p"))),
                Subsignal("mosi", Pins(_eem_pin(eem, 1, "p"))),
                Subsignal("miso", Pins(_eem_pin(eem, 2, "p"))),
                Subsignal("cs_n", Pins(_eem_pin(eem, 3, "p"))),
                IOStandard(iostandard),
            ),
            ("mirny{}_spi_n".format(eem), 0,
                Subsignal("clk", Pins(_eem_pin(eem, 0, "n"))),
                Subsignal("mosi", Pins(_eem_pin(eem, 1, "n"))),
                Subsignal("miso", Pins(_eem_pin(eem, 2, "n"))),
                Subsignal("cs_n", Pins(_eem_pin(eem, 3, "n"))),
                IOStandard(iostandard),
            ),
        ]
        for i in range(4):
            ios.append(
                ("mirny{}_io{}".format(eem, i), 0,
                    Subsignal("p", Pins(_eem_pin(eem, 4 + i, "p"))),
                    Subsignal("n", Pins(_eem_pin(eem, 4 + i, "n"))),
                    IOStandard(iostandard)
                ))
        return ios

    @classmethod
    def add_std(cls, target, eem, ttl_out_cls, iostandard="LVDS_25"):
        cls.add_extension(target, eem, iostandard=iostandard)

        phy = spi2.SPIMaster(
            target.platform.request("mirny{}_spi_p".format(eem)),
            target.platform.request("mirny{}_spi_n".format(eem)))
        target.submodules += phy
        target.rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=4))

        for i in range(4):
            pads = target.platform.request("mirny{}_io{}".format(eem, i))
            phy = ttl_out_cls(pads.p, pads.n)
            target.submodules += phy
            target.rtio_channels.append(rtio.Channel.from_phy(phy))


class Fastino(_EEM):
    @staticmethod
    def io(eem, iostandard="LVDS_25"):
        return [
            ("fastino{}_ser_{}".format(eem, pol), 0,
                Subsignal("clk", Pins(_eem_pin(eem, 0, pol))),
                Subsignal("mosi", Pins(*(_eem_pin(eem, i, pol)
                    for i in range(1, 7)))),
                Subsignal("miso", Pins(_eem_pin(eem, 7, pol))),
                IOStandard(iostandard),
            ) for pol in "pn"]

    @classmethod
    def add_std(cls, target, eem, iostandard="LVDS_25"):
        cls.add_extension(target, eem, iostandard=iostandard)

        phy = fastino.Fastino(target.platform.request("fastino{}_ser_p".format(eem)),
            target.platform.request("fastino{}_ser_n".format(eem)))
        target.submodules += phy
        target.rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=4))
