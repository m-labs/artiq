from migen import *
from migen.build.generic_platform import *
from migen.genlib.io import DifferentialOutput

from artiq.gateware import rtio
from artiq.gateware.rtio.phy import spi2, grabber
from artiq.gateware.suservo import servo, pads as servo_pads
from artiq.gateware.rtio.phy import servo as rtservo


def _eem_signal(i):
    n = "d{}".format(i)
    if i == 0:
        n += "_cc"
    return n


def _eem_pin(eem, i, pol):
    return "eem{}:{}_{}".format(eem, _eem_signal(i), pol)


class _EEM:
    @classmethod
    def add_extension(cls, target, eem, *args):
        name = cls.__name__
        target.platform.add_extension(cls.io(eem, *args))
        print("{} (EEM{}) starting at RTIO channel {}"
              .format(name, eem, len(target.rtio_channels)))


class DIO(_EEM):
    @staticmethod
    def io(eem):
        return [("dio{}".format(eem), i,
            Subsignal("p", Pins(_eem_pin(eem, i, "p"))),
            Subsignal("n", Pins(_eem_pin(eem, i, "n"))),
            IOStandard("LVDS_25"))
            for i in range(8)]

    @classmethod
    def add_std(cls, target, eem, ttl03_cls, ttl47_cls):
        cls.add_extension(target, eem)

        for i in range(4):
            pads = target.platform.request("dio{}".format(eem), i)
            phy = ttl03_cls(pads.p, pads.n)
            target.submodules += phy
            target.rtio_channels.append(rtio.Channel.from_phy(phy))
        for i in range(4):
            pads = target.platform.request("dio{}".format(eem), 4+i)
            phy = ttl47_cls(pads.p, pads.n)
            target.submodules += phy
            target.rtio_channels.append(rtio.Channel.from_phy(phy))


class Urukul(_EEM):
    @staticmethod
    def io(eem, eem_aux):
        ios = [
            ("urukul{}_spi_p".format(eem), 0,
                Subsignal("clk", Pins(_eem_pin(eem, 0, "p"))),
                Subsignal("mosi", Pins(_eem_pin(eem, 1, "p"))),
                Subsignal("miso", Pins(_eem_pin(eem, 2, "p"))),
                Subsignal("cs_n", Pins(
                    *(_eem_pin(eem, i + 3, "p") for i in range(3)))),
                IOStandard("LVDS_25"),
            ),
            ("urukul{}_spi_n".format(eem), 0,
                Subsignal("clk", Pins(_eem_pin(eem, 0, "n"))),
                Subsignal("mosi", Pins(_eem_pin(eem, 1, "n"))),
                Subsignal("miso", Pins(_eem_pin(eem, 2, "n"))),
                Subsignal("cs_n", Pins(
                    *(_eem_pin(eem, i + 3, "n") for i in range(3)))),
                IOStandard("LVDS_25"),
            ),
        ]
        ttls = [(6, eem, "io_update"),
                (7, eem, "dds_reset")]
        if eem_aux is not None:
            ttls += [(0, eem_aux, "sync_clk"),
                     (1, eem_aux, "sync_in"),
                     (2, eem_aux, "io_update_ret"),
                     (3, eem_aux, "nu_mosi3"),
                     (4, eem_aux, "sw0"),
                     (5, eem_aux, "sw1"),
                     (6, eem_aux, "sw2"),
                     (7, eem_aux, "sw3")]
        for i, j, sig in ttls:
            ios.append(
                ("urukul{}_{}".format(eem, sig), 0,
                    Subsignal("p", Pins(_eem_pin(j, i, "p"))),
                    Subsignal("n", Pins(_eem_pin(j, i, "n"))),
                    IOStandard("LVDS_25")
                ))
        return ios

    @staticmethod
    def io_qspi(eem0, eem1):
        ios = [
            ("urukul{}_spi_p".format(eem0), 0,
                Subsignal("clk", Pins(_eem_pin(eem0, 0, "p"))),
                Subsignal("mosi", Pins(_eem_pin(eem0, 1, "p"))),
                Subsignal("cs_n", Pins(
                    _eem_pin(eem0, 3, "p"), _eem_pin(eem0, 4, "p"))),
                IOStandard("LVDS_25"),
            ),
            ("urukul{}_spi_n".format(eem0), 0,
                Subsignal("clk", Pins(_eem_pin(eem0, 0, "n"))),
                Subsignal("mosi", Pins(_eem_pin(eem0, 1, "n"))),
                Subsignal("cs_n", Pins(
                    _eem_pin(eem0, 3, "n"), _eem_pin(eem0, 4, "n"))),
                IOStandard("LVDS_25"),
            ),
        ]
        ttls = [(6, eem0, "io_update"),
                (7, eem0, "dds_reset"),
                (4, eem1, "sw0"),
                (5, eem1, "sw1"),
                (6, eem1, "sw2"),
                (7, eem1, "sw3")]
        for i, j, sig in ttls:
            ios.append(
                ("urukul{}_{}".format(eem0, sig), 0,
                    Subsignal("p", Pins(_eem_pin(j, i, "p"))),
                    Subsignal("n", Pins(_eem_pin(j, i, "n"))),
                    IOStandard("LVDS_25")
                ))
        ios += [
            ("urukul{}_qspi_p".format(eem0), 0,
                Subsignal("cs", Pins(_eem_pin(eem0, 5, "p"))),
                Subsignal("clk", Pins(_eem_pin(eem0, 2, "p"))),
                Subsignal("mosi0", Pins(_eem_pin(eem1, 0, "p"))),
                Subsignal("mosi1", Pins(_eem_pin(eem1, 1, "p"))),
                Subsignal("mosi2", Pins(_eem_pin(eem1, 2, "p"))),
                Subsignal("mosi3", Pins(_eem_pin(eem1, 3, "p"))),
                IOStandard("LVDS_25"),
            ),
            ("urukul{}_qspi_n".format(eem0), 0,
                Subsignal("cs", Pins(_eem_pin(eem0, 5, "n"))),
                Subsignal("clk", Pins(_eem_pin(eem0, 2, "n"))),
                Subsignal("mosi0", Pins(_eem_pin(eem1, 0, "n"))),
                Subsignal("mosi1", Pins(_eem_pin(eem1, 1, "n"))),
                Subsignal("mosi2", Pins(_eem_pin(eem1, 2, "n"))),
                Subsignal("mosi3", Pins(_eem_pin(eem1, 3, "n"))),
                IOStandard("LVDS_25"),
            ),
        ]
        return ios

    @classmethod
    def add_std(cls, target, eem, eem_aux, ttl_out_cls):
        cls.add_extension(target, eem, eem_aux)

        phy = spi2.SPIMaster(target.platform.request("urukul{}_spi_p".format(eem)),
            target.platform.request("urukul{}_spi_n".format(eem)))
        target.submodules += phy
        target.rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=4))

        pads = target.platform.request("urukul{}_dds_reset".format(eem))
        target.specials += DifferentialOutput(0, pads.p, pads.n)

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
    def io(eem, eem_aux):
        ios = [
            ("sampler{}_adc_spi_p".format(eem), 0,
                Subsignal("clk", Pins(_eem_pin(eem, 0, "p"))),
                Subsignal("miso", Pins(_eem_pin(eem, 1, "p"))),
                IOStandard("LVDS_25"),
            ),
            ("sampler{}_adc_spi_n".format(eem), 0,
                Subsignal("clk", Pins(_eem_pin(eem, 0, "n"))),
                Subsignal("miso", Pins(_eem_pin(eem, 1, "n"))),
                IOStandard("LVDS_25"),
            ),
            ("sampler{}_pgia_spi_p".format(eem), 0,
                Subsignal("clk", Pins(_eem_pin(eem, 4, "p"))),
                Subsignal("mosi", Pins(_eem_pin(eem, 5, "p"))),
                Subsignal("miso", Pins(_eem_pin(eem, 6, "p"))),
                Subsignal("cs_n", Pins(_eem_pin(eem, 7, "p"))),
                IOStandard("LVDS_25"),
            ),
            ("sampler{}_pgia_spi_n".format(eem), 0,
                Subsignal("clk", Pins(_eem_pin(eem, 4, "n"))),
                Subsignal("mosi", Pins(_eem_pin(eem, 5, "n"))),
                Subsignal("miso", Pins(_eem_pin(eem, 6, "n"))),
                Subsignal("cs_n", Pins(_eem_pin(eem, 7, "n"))),
                IOStandard("LVDS_25"),
            ),
        ] + [
            ("sampler{}_{}".format(eem, sig), 0,
                Subsignal("p", Pins(_eem_pin(j, i, "p"))),
                Subsignal("n", Pins(_eem_pin(j, i, "n"))),
                IOStandard("LVDS_25")
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
                    IOStandard("LVDS_25"),
                ),
                ("sampler{}_adc_data_n".format(eem), 0,
                    Subsignal("clkout", Pins(_eem_pin(eem_aux, 0, "n"))),
                    Subsignal("sdoa", Pins(_eem_pin(eem_aux, 1, "n"))),
                    Subsignal("sdob", Pins(_eem_pin(eem_aux, 2, "n"))),
                    Subsignal("sdoc", Pins(_eem_pin(eem_aux, 3, "n"))),
                    Subsignal("sdod", Pins(_eem_pin(eem_aux, 4, "n"))),
                    Misc("DIFF_TERM=TRUE"),
                    IOStandard("LVDS_25"),
                ),
            ]
        return ios

    @classmethod
    def add_std(cls, target, eem, eem_aux, ttl_out_cls):
        cls.add_extension(target, eem, eem_aux)

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
    def io(eem):
        return [
            ("novogorny{}_spi_p".format(eem), 0,
                Subsignal("clk", Pins(_eem_pin(eem, 0, "p"))),
                Subsignal("mosi", Pins(_eem_pin(eem, 1, "p"))),
                Subsignal("miso", Pins(_eem_pin(eem, 2, "p"))),
                Subsignal("cs_n", Pins(
                    _eem_pin(eem, 3, "p"), _eem_pin(eem, 4, "p"))),
                IOStandard("LVDS_25"),
            ),
            ("novogorny{}_spi_n".format(eem), 0,
                Subsignal("clk", Pins(_eem_pin(eem, 0, "n"))),
                Subsignal("mosi", Pins(_eem_pin(eem, 1, "n"))),
                Subsignal("miso", Pins(_eem_pin(eem, 2, "n"))),
                Subsignal("cs_n", Pins(
                    _eem_pin(eem, 3, "n"), _eem_pin(eem, 4, "n"))),
                IOStandard("LVDS_25"),
            ),
        ] + [
            ("novogorny{}_{}".format(eem, sig), 0,
                Subsignal("p", Pins(_eem_pin(j, i, "p"))),
                Subsignal("n", Pins(_eem_pin(j, i, "n"))),
                IOStandard("LVDS_25")
            ) for i, j, sig in [
                (5, eem, "cnv"),
                (6, eem, "busy"),
                (7, eem, "scko"),
                ]
        ]

    @classmethod
    def add_std(cls, target, eem, ttl_out_cls):
        cls.add_extension(target, eem)

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
    def io(eem):
        return [
            ("zotino{}_spi_p".format(eem), 0,
                Subsignal("clk", Pins(_eem_pin(eem, 0, "p"))),
                Subsignal("mosi", Pins(_eem_pin(eem, 1, "p"))),
                Subsignal("miso", Pins(_eem_pin(eem, 2, "p"))),
                Subsignal("cs_n", Pins(
                    _eem_pin(eem, 3, "p"), _eem_pin(eem, 4, "p"))),
                IOStandard("LVDS_25"),
            ),
            ("zotino{}_spi_n".format(eem), 0,
                Subsignal("clk", Pins(_eem_pin(eem, 0, "n"))),
                Subsignal("mosi", Pins(_eem_pin(eem, 1, "n"))),
                Subsignal("miso", Pins(_eem_pin(eem, 2, "n"))),
                Subsignal("cs_n", Pins(
                    _eem_pin(eem, 3, "n"), _eem_pin(eem, 4, "n"))),
                IOStandard("LVDS_25"),
            ),
        ] + [
            ("zotino{}_{}".format(eem, sig), 0,
                    Subsignal("p", Pins(_eem_pin(j, i, "p"))),
                    Subsignal("n", Pins(_eem_pin(j, i, "n"))),
                    IOStandard("LVDS_25")
            ) for i, j, sig in [
                (5, eem, "ldac_n"),
                (6, eem, "busy"),
                (7, eem, "clr_n"),
                ]
        ]

    @classmethod
    def add_std(cls, target, eem, ttl_out_cls):
        cls.add_extension(target, eem)

        phy = spi2.SPIMaster(target.platform.request("zotino{}_spi_p".format(eem)),
            target.platform.request("zotino{}_spi_n".format(eem)))
        target.submodules += phy
        target.rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=4))

        for signal in "ldac_n clr_n".split():
            pads = target.platform.request("zotino{}_{}".format(eem, signal))
            phy = ttl_out_cls(pads.p, pads.n)
            target.submodules += phy
            target.rtio_channels.append(rtio.Channel.from_phy(phy))


class Grabber(_EEM):
    @staticmethod
    def io(eem, eem_aux):
        ios = [
            ("grabber{}_video".format(eem), 0,
                Subsignal("clk_p", Pins(_eem_pin(eem, 0, "p"))),
                Subsignal("clk_n", Pins(_eem_pin(eem, 0, "n"))),
                Subsignal("sdi_p", Pins(*[_eem_pin(eem, i, "p") for i in range(1, 5)])),
                Subsignal("sdi_n", Pins(*[_eem_pin(eem, i, "n") for i in range(1, 5)])),
                IOStandard("LVDS_25")
            ),
            ("grabber{}_cc0".format(eem), 0,
                Subsignal("p", Pins(_eem_pin(eem_aux, 5, "p"))),
                Subsignal("n", Pins(_eem_pin(eem_aux, 5, "n"))),
                IOStandard("LVDS_25")
            ),
            ("grabber{}_cc1".format(eem), 0,
                Subsignal("p", Pins(_eem_pin(eem_aux, 6, "p"))),
                Subsignal("n", Pins(_eem_pin(eem_aux, 6, "n"))),
                IOStandard("LVDS_25")
            ),
            ("grabber{}_cc2".format(eem), 0,
                Subsignal("p", Pins(_eem_pin(eem_aux, 7, "p"))),
                Subsignal("n", Pins(_eem_pin(eem_aux, 7, "n"))),
                IOStandard("LVDS_25")
            ),
        ]
        if eem_aux is not None:
            ios += [
                ("grabber{}_video_m".format(eem), 0,
                    Subsignal("clk_p", Pins(_eem_pin(eem_aux, 0, "p"))),
                    Subsignal("clk_n", Pins(_eem_pin(eem_aux, 0, "n"))),
                    Subsignal("sdi_p", Pins(*[_eem_pin(eem_aux, i, "p") for i in range(1, 5)])),
                    Subsignal("sdi_n", Pins(*[_eem_pin(eem_aux, i, "n") for i in range(1, 5)])),
                    IOStandard("LVDS_25")
                ),
                ("grabber{}_serrx".format(eem), 0,
                    Subsignal("p", Pins(_eem_pin(eem_aux, 5, "p"))),
                    Subsignal("n", Pins(_eem_pin(eem_aux, 5, "n"))),
                    IOStandard("LVDS_25")
                ),
                ("grabber{}_sertx".format(eem), 0,
                    Subsignal("p", Pins(_eem_pin(eem_aux, 6, "p"))),
                    Subsignal("n", Pins(_eem_pin(eem_aux, 6, "n"))),
                    IOStandard("LVDS_25")
                ),
                ("grabber{}_cc3".format(eem), 0,
                    Subsignal("p", Pins(_eem_pin(eem_aux, 7, "p"))),
                    Subsignal("n", Pins(_eem_pin(eem_aux, 7, "n"))),
                    IOStandard("LVDS_25")
                ),
            ]
        return ios

    @classmethod
    def add_std(cls, target, eem, eem_aux=None, ttl_out_cls=None):
        cls.add_extension(target, eem, eem_aux)

        phy = grabber.Grabber(target.platform.request(
            "grabber{}_video".format(eem)))
        name = "grabber{}".format(len(target.grabber_csr_group))
        setattr(target.submodules, name, phy)
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
    def io(*eems):
        assert len(eems) == 6
        return (Sampler.io(*eems[0:2])
                + Urukul.io_qspi(*eems[2:4])
                + Urukul.io_qspi(*eems[4:6]))

    @classmethod
    def add_std(cls, target, eems_sampler, eems_urukul0, eems_urukul1,
                t_rtt=8, clk=1, shift=11, profile=5):
        """ Adds an 8-channel Sampler-Urukul servo to target.

        :param t_rtt: upper estimate for clock round-trip propagation time from
            sck at the FPGA to clkout at the FPGA, measured in RTIO coarse
            cycles (default: 8). This is the sum of the round-trip cabling
            delay and the 8ns max propagation delay on Sampler. With all
            other parameters at their default values, increasing t_rtt beyond 8
            increases the servo latency
        :param clk: DDS SPI clock cycle half-width in RTIO coarse cycles
            (default: 1)
        :param shift: fixed-point scaling factor for IIR coefficients
            (default: 11)
        :param profile: log2 of the number of profiles for each DDS channel
            (default: 5)
        """

        cls.add_extension(
            target, *(eems_sampler + eems_urukul0 + eems_urukul1))
        eem_sampler = "sampler{}".format(eems_sampler[0])
        eem_urukul0 = "urukul{}".format(eems_urukul0[0])
        eem_urukul1 = "urukul{}".format(eems_urukul1[0])

        sampler_pads = servo_pads.SamplerPads(target.platform, eem_sampler)
        urukul_pads = servo_pads.UrukulPads(
                target.platform, eem_urukul0, eem_urukul1)
        # timings in units of RTIO coarse period
        adc_p = servo.ADCParams(width=16, channels=8, lanes=4, t_cnvh=4,
                                # account for SCK pipeline latency
                                t_conv=57 - 4, t_rtt=t_rtt)
        iir_p = servo.IIRWidths(state=25, coeff=18, adc=16, asf=14, word=16,
                                accu=48, shift=shift, channel=3,
                                profile=profile)
        dds_p = servo.DDSParams(width=8 + 32 + 16 + 16,
                                channels=adc_p.channels, clk=clk)
        su = servo.Servo(sampler_pads, urukul_pads, adc_p, iir_p, dds_p)
        su = ClockDomainsRenamer("rio_phy")(su)
        target.submodules += sampler_pads, urukul_pads, su

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

        phy = spi2.SPIMaster(
            target.platform.request("{}_spi_p".format(eem_urukul0)),
            target.platform.request("{}_spi_n".format(eem_urukul0)))
        target.submodules += phy
        target.rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=4))

        pads = target.platform.request("{}_dds_reset".format(eem_urukul0))
        target.specials += DifferentialOutput(0, pads.p, pads.n)

        for i, signal in enumerate("sw0 sw1 sw2 sw3".split()):
            pads = target.platform.request("{}_{}".format(eem_urukul0, signal))
            target.specials += DifferentialOutput(
                su.iir.ctrl[i].en_out, pads.p, pads.n)

        phy = spi2.SPIMaster(
            target.platform.request("{}_spi_p".format(eem_urukul1)),
            target.platform.request("{}_spi_n".format(eem_urukul1)))
        target.submodules += phy
        target.rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=4))

        pads = target.platform.request("{}_dds_reset".format(eem_urukul1))
        target.specials += DifferentialOutput(0, pads.p, pads.n)

        for i, signal in enumerate("sw0 sw1 sw2 sw3".split()):
            pads = target.platform.request("{}_{}".format(eem_urukul1, signal))
            target.specials += DifferentialOutput(
                su.iir.ctrl[i + 4].en_out, pads.p, pads.n)
