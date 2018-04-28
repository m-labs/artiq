#!/usr/bin/env python3

import argparse

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.genlib.cdc import MultiReg
from migen.build.generic_platform import *
from migen.build.xilinx.vivado import XilinxVivadoToolchain
from migen.build.xilinx.ise import XilinxISEToolchain
from migen.genlib.io import DifferentialOutput, DifferentialInput

from misoc.interconnect.csr import *
from misoc.cores import gpio
from misoc.cores.a7_gtp import *
from misoc.targets.kasli import (BaseSoC, MiniSoC,
    soc_kasli_args, soc_kasli_argdict)
from misoc.integration.builder import builder_args, builder_argdict

from artiq.gateware.amp import AMPSoC
from artiq.gateware import rtio
from artiq.gateware.rtio.phy import (
        ttl_simple, ttl_serdes_7series, spi2, servo as rtservo)
from artiq.gateware.suservo import servo, pads as servo_pads
from artiq.gateware.drtio.transceiver import gtp_7series
from artiq.gateware.drtio.siphaser import SiPhaser7Series
from artiq.gateware.drtio.rx_synchronizer import XilinxRXSynchronizer
from artiq.gateware.drtio import DRTIOMaster, DRTIOSatellite
from artiq.build_soc import build_artiq_soc
from artiq import __version__ as artiq_version


class _RTIOCRG(Module, AutoCSR):
    def __init__(self, platform, rtio_internal_clk):
        self._clock_sel = CSRStorage()
        self._pll_reset = CSRStorage(reset=1)
        self._pll_locked = CSRStatus()
        self.clock_domains.cd_rtio = ClockDomain()
        self.clock_domains.cd_rtiox4 = ClockDomain(reset_less=True)

        rtio_external_clk = Signal()
        clk_synth_se = Signal()
        clk_synth = platform.request("si5324_clkout_fabric")
        platform.add_period_constraint(clk_synth.p, 8.0)
        self.specials += [
            Instance("IBUFGDS",
                p_DIFF_TERM="TRUE", p_IBUF_LOW_PWR="TRUE",
                i_I=clk_synth.p, i_IB=clk_synth.n, o_O=clk_synth_se),
            Instance("BUFG", i_I=clk_synth_se, o_O=rtio_external_clk),
        ]
        platform.add_false_path_constraints(
                rtio_external_clk, rtio_internal_clk)

        pll_locked = Signal()
        rtio_clk = Signal()
        rtiox4_clk = Signal()
        ext_clkout_clk = Signal()
        self.specials += [
            Instance("PLLE2_ADV",
                     p_STARTUP_WAIT="FALSE", o_LOCKED=pll_locked,

                     p_REF_JITTER1=0.01,
                     p_CLKIN1_PERIOD=8.0, p_CLKIN2_PERIOD=8.0,
                     i_CLKIN1=rtio_internal_clk, i_CLKIN2=rtio_external_clk,
                     # Warning: CLKINSEL=0 means CLKIN2 is selected
                     i_CLKINSEL=~self._clock_sel.storage,

                     # VCO @ 1GHz when using 125MHz input
                     p_CLKFBOUT_MULT=8, p_DIVCLK_DIVIDE=1,
                     i_CLKFBIN=self.cd_rtio.clk,
                     i_RST=self._pll_reset.storage,

                     o_CLKFBOUT=rtio_clk,

                     p_CLKOUT0_DIVIDE=2, p_CLKOUT0_PHASE=0.0,
                     o_CLKOUT0=rtiox4_clk),
            Instance("BUFG", i_I=rtio_clk, o_O=self.cd_rtio.clk),
            Instance("BUFG", i_I=rtiox4_clk, o_O=self.cd_rtiox4.clk),

            AsyncResetSynchronizer(self.cd_rtio, ~pll_locked),
            MultiReg(pll_locked, self._pll_locked.status)
        ]


def fix_serdes_timing_path(platform):
    # ignore timing of path from OSERDESE2 through the pad to ISERDESE2
    platform.add_platform_command(
        "set_false_path -quiet "
        "-through [get_pins -filter {{REF_PIN_NAME == OQ || REF_PIN_NAME == TQ}} "
            "-of [get_cells -filter {{REF_NAME == OSERDESE2}}]] "
        "-to [get_pins -filter {{REF_PIN_NAME == D}} "
            "-of [get_cells -filter {{REF_NAME == ISERDESE2}}]]"
    )


class _StandaloneBase(MiniSoC, AMPSoC):
    mem_map = {
        "cri_con":       0x10000000,
        "rtio":          0x20000000,
        "rtio_dma":      0x30000000,
        "mailbox":       0x70000000
    }
    mem_map.update(MiniSoC.mem_map)

    def __init__(self, **kwargs):
        MiniSoC.__init__(self,
                         cpu_type="or1k",
                         sdram_controller_type="minicon",
                         l2_size=128*1024,
                         ident=artiq_version,
                         ethmac_nrxslots=4,
                         ethmac_ntxslots=4,
                         **kwargs)
        AMPSoC.__init__(self)

        self.submodules.leds = gpio.GPIOOut(Cat(
            self.platform.request("user_led", 0)))
        self.csr_devices.append("leds")

        i2c = self.platform.request("i2c")
        self.submodules.i2c = gpio.GPIOTristate([i2c.scl, i2c.sda])
        self.csr_devices.append("i2c")
        self.config["I2C_BUS_COUNT"] = 1
        self.config["HAS_SI5324"] = None
        self.config["SI5324_SOFT_RESET"] = None

    def add_rtio(self, rtio_channels):
        self.submodules.rtio_crg = _RTIOCRG(self.platform, self.crg.cd_sys.clk)
        self.csr_devices.append("rtio_crg")
        fix_serdes_timing_path(self.platform)
        self.submodules.rtio_core = rtio.Core(rtio_channels)
        self.csr_devices.append("rtio_core")
        self.submodules.rtio = rtio.KernelInitiator()
        self.submodules.rtio_dma = ClockDomainsRenamer("sys_kernel")(
            rtio.DMA(self.get_native_sdram_if()))
        self.register_kernel_cpu_csrdevice("rtio")
        self.register_kernel_cpu_csrdevice("rtio_dma")
        self.submodules.cri_con = rtio.CRIInterconnectShared(
            [self.rtio.cri, self.rtio_dma.cri],
            [self.rtio_core.cri])
        self.register_kernel_cpu_csrdevice("cri_con")
        self.submodules.rtio_moninj = rtio.MonInj(rtio_channels)
        self.csr_devices.append("rtio_moninj")

        self.platform.add_false_path_constraints(
            self.crg.cd_sys.clk,
            self.rtio_crg.cd_rtio.clk)

        self.submodules.rtio_analyzer = rtio.Analyzer(self.rtio_core.cri,
                                                      self.get_native_sdram_if())
        self.csr_devices.append("rtio_analyzer")


def _eem_signal(i):
    n = "d{}".format(i)
    if i == 0:
        n += "_cc"
    return n


def _eem_pin(eem, i, pol):
    return "{}:{}_{}".format(eem, _eem_signal(i), pol)


def _dio(eem):
    return [(eem, i,
        Subsignal("p", Pins(_eem_pin(eem, i, "p"))),
        Subsignal("n", Pins(_eem_pin(eem, i, "n"))),
        IOStandard("LVDS_25"))
        for i in range(8)]


def _sampler(eem, eem_aux=None):
    ios = [
        ("{}_adc_spi_p".format(eem), 0,
            Subsignal("clk", Pins(_eem_pin(eem, 0, "p"))),
            Subsignal("miso", Pins(_eem_pin(eem, 1, "p"))),
            IOStandard("LVDS_25"),
        ),
        ("{}_adc_spi_n".format(eem), 0,
            Subsignal("clk", Pins(_eem_pin(eem, 0, "n"))),
            Subsignal("miso", Pins(_eem_pin(eem, 1, "n"))),
            IOStandard("LVDS_25"),
        ),
        ("{}_pgia_spi_p".format(eem), 0,
            Subsignal("clk", Pins(_eem_pin(eem, 4, "p"))),
            Subsignal("mosi", Pins(_eem_pin(eem, 5, "p"))),
            Subsignal("miso", Pins(_eem_pin(eem, 6, "p"))),
            Subsignal("cs_n", Pins(_eem_pin(eem, 7, "p"))),
            IOStandard("LVDS_25"),
        ),
        ("{}_pgia_spi_n".format(eem), 0,
            Subsignal("clk", Pins(_eem_pin(eem, 4, "n"))),
            Subsignal("mosi", Pins(_eem_pin(eem, 5, "n"))),
            Subsignal("miso", Pins(_eem_pin(eem, 6, "n"))),
            Subsignal("cs_n", Pins(_eem_pin(eem, 7, "n"))),
            IOStandard("LVDS_25"),
        ),
        ] + [
        ("{}_{}".format(eem, sig), 0,
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
            ("{}_adc_data_p".format(eem), 0,
                Subsignal("clkout", Pins(_eem_pin(eem_aux, 0, "p"))),
                Subsignal("sdoa", Pins(_eem_pin(eem_aux, 1, "p"))),
                Subsignal("sdob", Pins(_eem_pin(eem_aux, 2, "p"))),
                Subsignal("sdoc", Pins(_eem_pin(eem_aux, 3, "p"))),
                Subsignal("sdod", Pins(_eem_pin(eem_aux, 4, "p"))),
                IOStandard("LVDS_25"),
            ),
            ("{}_adc_data_n".format(eem), 0,
                Subsignal("clkout", Pins(_eem_pin(eem_aux, 0, "n"))),
                Subsignal("sdoa", Pins(_eem_pin(eem_aux, 1, "n"))),
                Subsignal("sdob", Pins(_eem_pin(eem_aux, 2, "n"))),
                Subsignal("sdoc", Pins(_eem_pin(eem_aux, 3, "n"))),
                Subsignal("sdod", Pins(_eem_pin(eem_aux, 4, "n"))),
                IOStandard("LVDS_25"),
            ),
        ]
    return ios


def _novogorny(eem):
    return [
        ("{}_spi_p".format(eem), 0,
            Subsignal("clk", Pins(_eem_pin(eem, 0, "p"))),
            Subsignal("mosi", Pins(_eem_pin(eem, 1, "p"))),
            Subsignal("miso", Pins(_eem_pin(eem, 2, "p"))),
            Subsignal("cs_n", Pins(
                _eem_pin(eem, 3, "p"), _eem_pin(eem, 4, "p"))),
            IOStandard("LVDS_25"),
        ),
        ("{}_spi_n".format(eem), 0,
            Subsignal("clk", Pins(_eem_pin(eem, 0, "n"))),
            Subsignal("mosi", Pins(_eem_pin(eem, 1, "n"))),
            Subsignal("miso", Pins(_eem_pin(eem, 2, "n"))),
            Subsignal("cs_n", Pins(
                _eem_pin(eem, 3, "n"), _eem_pin(eem, 4, "n"))),
            IOStandard("LVDS_25"),
        ),
        ] + [
        ("{}_{}".format(eem, sig), 0,
            Subsignal("p", Pins(_eem_pin(j, i, "p"))),
            Subsignal("n", Pins(_eem_pin(j, i, "n"))),
            IOStandard("LVDS_25")
        ) for i, j, sig in [
            (5, eem, "cnv"),
            (6, eem, "busy"),
            (7, eem, "scko"),
            ]
        ]


def _zotino(eem):
    return [
        ("{}_spi_p".format(eem), 0,
            Subsignal("clk", Pins(_eem_pin(eem, 0, "p"))),
            Subsignal("mosi", Pins(_eem_pin(eem, 1, "p"))),
            Subsignal("miso", Pins(_eem_pin(eem, 2, "p"))),
            Subsignal("cs_n", Pins(
                _eem_pin(eem, 3, "p"), _eem_pin(eem, 4, "p"))),
            IOStandard("LVDS_25"),
        ),
        ("{}_spi_n".format(eem), 0,
            Subsignal("clk", Pins(_eem_pin(eem, 0, "n"))),
            Subsignal("mosi", Pins(_eem_pin(eem, 1, "n"))),
            Subsignal("miso", Pins(_eem_pin(eem, 2, "n"))),
            Subsignal("cs_n", Pins(
                _eem_pin(eem, 3, "n"), _eem_pin(eem, 4, "n"))),
            IOStandard("LVDS_25"),
        ),
        ] + [
        ("{}_{}".format(eem, sig), 0,
                Subsignal("p", Pins(_eem_pin(j, i, "p"))),
                Subsignal("n", Pins(_eem_pin(j, i, "n"))),
                IOStandard("LVDS_25")
        ) for i, j, sig in [
            (5, eem, "ldac_n"),
            (6, eem, "busy"),
            (7, eem, "clr_n"),
            ]
        ]


def _urukul(eem, eem_aux=None):
    ios = [
        ("{}_spi_p".format(eem), 0,
            Subsignal("clk", Pins(_eem_pin(eem, 0, "p"))),
            Subsignal("mosi", Pins(_eem_pin(eem, 1, "p"))),
            Subsignal("miso", Pins(_eem_pin(eem, 2, "p"))),
            Subsignal("cs_n", Pins(
                *(_eem_pin(eem, i + 3, "p") for i in range(3)))),
            IOStandard("LVDS_25"),
        ),
        ("{}_spi_n".format(eem), 0,
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
            ("{}_{}".format(eem, sig), 0,
                Subsignal("p", Pins(_eem_pin(j, i, "p"))),
                Subsignal("n", Pins(_eem_pin(j, i, "n"))),
                IOStandard("LVDS_25")
            ))
    return ios


def _urukul_qspi(eem0, eem1):
    ios = [
        ("{}_spi_p".format(eem0), 0,
            Subsignal("clk", Pins(_eem_pin(eem0, 0, "p"))),
            Subsignal("mosi", Pins(_eem_pin(eem0, 1, "p"))),
            Subsignal("cs_n", Pins(
                _eem_pin(eem0, 3, "p"), _eem_pin(eem0, 4, "p"))),
            IOStandard("LVDS_25"),
        ),
        ("{}_spi_n".format(eem0), 0,
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
            ("{}_{}".format(eem0, sig), 0,
                Subsignal("p", Pins(_eem_pin(j, i, "p"))),
                Subsignal("n", Pins(_eem_pin(j, i, "n"))),
                IOStandard("LVDS_25")
            ))
    ios += [
        ("{}_qspi_p".format(eem0), 0,
            Subsignal("cs", Pins(_eem_pin(eem0, 5, "p"))),
            Subsignal("clk", Pins(_eem_pin(eem0, 2, "p"))),
            Subsignal("mosi0", Pins(_eem_pin(eem1, 0, "p"))),
            Subsignal("mosi1", Pins(_eem_pin(eem1, 1, "p"))),
            Subsignal("mosi2", Pins(_eem_pin(eem1, 2, "p"))),
            Subsignal("mosi3", Pins(_eem_pin(eem1, 3, "p"))),
            IOStandard("LVDS_25"),
        ),
        ("{}_qspi_n".format(eem0), 0,
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


class Opticlock(_StandaloneBase):
    """
    Opticlock extension variant configuration
    """
    def __init__(self, **kwargs):
        _StandaloneBase.__init__(self, **kwargs)

        self.config["SI5324_AS_SYNTHESIZER"] = None
        # self.config["SI5324_EXT_REF"] = None
        self.config["RTIO_FREQUENCY"] = "125.0"

        platform = self.platform
        platform.add_extension(_dio("eem0"))
        platform.add_extension(_dio("eem1"))
        platform.add_extension(_dio("eem2"))
        platform.add_extension(_novogorny("eem3"))
        platform.add_extension(_urukul("eem5", "eem4"))
        platform.add_extension(_urukul("eem6"))
        platform.add_extension(_zotino("eem7"))

        try:
            # EEM clock fan-out from Si5324, not MMCX, only Kasli/v1.0
            self.comb += platform.request("clk_sel").eq(1)
        except ConstraintError:
            pass

        rtio_channels = []
        for i in range(24):
            eem, port = divmod(i, 8)
            pads = platform.request("eem{}".format(eem), port)
            if i < 4:
                cls = ttl_serdes_7series.InOut_8X
            else:
                cls = ttl_serdes_7series.Output_8X
            phy = cls(pads.p, pads.n)
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))

        # EEM3: Novogorny
        phy = spi2.SPIMaster(self.platform.request("eem3_spi_p"),
                self.platform.request("eem3_spi_n"))
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=16))

        for signal in "cnv".split():
            pads = platform.request("eem3_{}".format(signal))
            phy = ttl_serdes_7series.Output_8X(pads.p, pads.n)
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))

        # EEM5 + EEM4: Urukul
        phy = spi2.SPIMaster(self.platform.request("eem5_spi_p"),
                self.platform.request("eem5_spi_n"))
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=4))

        pads = platform.request("eem5_dds_reset")
        self.specials += DifferentialOutput(0, pads.p, pads.n)

        for signal in "io_update sw0 sw1 sw2 sw3".split():
            pads = platform.request("eem5_{}".format(signal))
            phy = ttl_serdes_7series.Output_8X(pads.p, pads.n)
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))

        for i in (1, 2):
            sfp_ctl = platform.request("sfp_ctl", i)
            phy = ttl_simple.Output(sfp_ctl.led)
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))

        # EEM6: Urukul
        phy = spi2.SPIMaster(self.platform.request("eem6_spi_p"),
                self.platform.request("eem6_spi_n"))
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=4))

        for signal in "io_update".split():
            pads = platform.request("eem6_{}".format(signal))
            phy = ttl_serdes_7series.Output_8X(pads.p, pads.n)
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))

        pads = platform.request("eem6_dds_reset")
        self.specials += DifferentialOutput(0, pads.p, pads.n)

        # EEM7: Zotino
        phy = spi2.SPIMaster(self.platform.request("eem7_spi_p"),
                self.platform.request("eem7_spi_n"))
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=4))

        for signal in "ldac_n clr_n".split():
            pads = platform.request("eem7_{}".format(signal))
            phy = ttl_serdes_7series.Output_8X(pads.p, pads.n)
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))

        self.config["HAS_RTIO_LOG"] = None
        self.config["RTIO_LOG_CHANNEL"] = len(rtio_channels)
        rtio_channels.append(rtio.LogChannel())

        self.add_rtio(rtio_channels)


class SUServo(_StandaloneBase):
    """
    SUServo (Sampler-Urukul-Servo) extension variant configuration
    """
    def __init__(self, **kwargs):
        _StandaloneBase.__init__(self, **kwargs)

        self.config["SI5324_AS_SYNTHESIZER"] = None
        # self.config["SI5324_EXT_REF"] = None
        self.config["RTIO_FREQUENCY"] = "125.0"

        platform = self.platform
        platform.add_extension(_dio("eem0"))
        platform.add_extension(_dio("eem1"))
        platform.add_extension(_sampler("eem3", "eem2"))
        platform.add_extension(_urukul_qspi("eem5", "eem4"))
        platform.add_extension(_urukul_qspi("eem7", "eem6"))

        try:
            # EEM clock fan-out from Si5324, not MMCX, only Kasli/v1.0
            self.comb += platform.request("clk_sel").eq(1)
        except ConstraintError:
            pass

        rtio_channels = []
        for i in range(16):
            eem, port = divmod(i, 8)
            pads = platform.request("eem{}".format(eem), port)
            if i < 4:
                cls = ttl_serdes_7series.InOut_8X
            else:
                cls = ttl_serdes_7series.Output_8X
            phy = cls(pads.p, pads.n)
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))

        # EEM3, EEM2: Sampler
        sampler_pads = servo_pads.SamplerPads(self.platform, "eem3")
        # EEM5, EEM4 and EEM7, EEM6: Urukul
        urukul_pads = servo_pads.UrukulPads(self.platform,
                "eem5", "eem7")
        adc_p = servo.ADCParams(width=16, channels=8, lanes=4, t_cnvh=4,
                # account for SCK pipeline latency
                t_conv=57 - 4, t_rtt=4 + 4)
        iir_p = servo.IIRWidths(state=25, coeff=18, adc=16, asf=14, word=16,
                accu=48, shift=11, channel=3, profile=5)
        dds_p = servo.DDSParams(width=8 + 32 + 16 + 16,
                channels=adc_p.channels, clk=1)
        su = servo.Servo(sampler_pads, urukul_pads, adc_p, iir_p, dds_p)
        su = ClockDomainsRenamer("rio_phy")(su)
        self.submodules += sampler_pads, urukul_pads, su

        ctrls = [rtservo.RTServoCtrl(ctrl) for ctrl in su.iir.ctrl]
        self.submodules += ctrls
        rtio_channels.extend(rtio.Channel.from_phy(ctrl) for ctrl in ctrls)
        mem = rtservo.RTServoMem(iir_p, su)
        self.submodules += mem
        rtio_channels.append(rtio.Channel.from_phy(mem, ififo_depth=4))

        # EEM3: Sampler
        phy = spi2.SPIMaster(self.platform.request("eem3_pgia_spi_p"),
                self.platform.request("eem3_pgia_spi_n"))
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=4))

        # EEM5 + EEM4: Urukul
        phy = spi2.SPIMaster(self.platform.request("eem5_spi_p"),
                self.platform.request("eem5_spi_n"))
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=4))

        pads = platform.request("eem5_dds_reset")
        self.specials += DifferentialOutput(0, pads.p, pads.n)

        for i, signal in enumerate("sw0 sw1 sw2 sw3".split()):
            pads = platform.request("eem5_{}".format(signal))
            self.specials += DifferentialOutput(
                    su.iir.ctrl[i].en_out,
                    pads.p, pads.n)

        # EEM7 + EEM6: Urukul
        phy = spi2.SPIMaster(self.platform.request("eem7_spi_p"),
                self.platform.request("eem7_spi_n"))
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=4))

        pads = platform.request("eem7_dds_reset")
        self.specials += DifferentialOutput(0, pads.p, pads.n)

        for i, signal in enumerate("sw0 sw1 sw2 sw3".split()):
            pads = platform.request("eem7_{}".format(signal))
            self.specials += DifferentialOutput(
                    su.iir.ctrl[i + 4].en_out,
                    pads.p, pads.n)

        for i in (1, 2):
            sfp_ctl = platform.request("sfp_ctl", i)
            phy = ttl_simple.Output(sfp_ctl.led)
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))

        self.config["HAS_RTIO_LOG"] = None
        self.config["RTIO_LOG_CHANNEL"] = len(rtio_channels)
        rtio_channels.append(rtio.LogChannel())

        self.add_rtio(rtio_channels)

        platform.add_false_path_constraints(
            sampler_pads.clkout_p,
            self.rtio_crg.cd_rtio.clk)
        platform.add_false_path_constraints(
            sampler_pads.clkout_p,
            self.crg.cd_sys.clk)


class SYSU(_StandaloneBase):
    def __init__(self, **kwargs):
        _StandaloneBase.__init__(self, **kwargs)

        self.config["SI5324_AS_SYNTHESIZER"] = None
        self.config["RTIO_FREQUENCY"] = "125.0"

        platform = self.platform
        platform.add_extension(_urukul("eem1", "eem0"))
        platform.add_extension(_dio("eem2"))
        platform.add_extension(_dio("eem3"))
        platform.add_extension(_dio("eem4"))
        platform.add_extension(_dio("eem5"))
        platform.add_extension(_dio("eem6"))

        # EEM clock fan-out from Si5324, not MMCX
        self.comb += platform.request("clk_sel").eq(1)

        # EEM2-6: TTL
        rtio_channels = []
        for i in range(40):
            eem_offset, port = divmod(i, 8)
            pads = platform.request("eem{}".format(2 + eem_offset), port)
            phy = ttl_serdes_7series.InOut_8X(pads.p, pads.n)
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))

        # EEM0, EEM1: Urukul
        phy = spi2.SPIMaster(self.platform.request("eem1_spi_p"),
                self.platform.request("eem1_spi_n"))
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=4))

        pads = platform.request("eem1_dds_reset")
        self.specials += DifferentialOutput(0, pads.p, pads.n)

        for signal in "io_update sw0 sw1 sw2 sw3".split():
            pads = platform.request("eem1_{}".format(signal))
            phy = ttl_serdes_7series.Output_8X(pads.p, pads.n)
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))

        for i in (1, 2):
            sfp_ctl = platform.request("sfp_ctl", i)
            phy = ttl_simple.Output(sfp_ctl.led)
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))

        self.config["HAS_RTIO_LOG"] = None
        self.config["RTIO_LOG_CHANNEL"] = len(rtio_channels)
        rtio_channels.append(rtio.LogChannel())

        self.add_rtio(rtio_channels)


class MITLL(_StandaloneBase):
    def __init__(self, hw_rev=None, **kwargs):
        if hw_rev is None:
            hw_rev = "v1.1"
        _StandaloneBase.__init__(self, hw_rev=hw_rev, **kwargs)

        self.config["SI5324_AS_SYNTHESIZER"] = None
        self.config["RTIO_FREQUENCY"] = "125.0"

        platform = self.platform
        # TODO: grabber on eem0->eemB eem1->eemA
        platform.add_extension(_urukul("eem3", "eem2"))
        platform.add_extension(_dio("eem4"))
        platform.add_extension(_zotino("eem5"))
        platform.add_extension(_zotino("eem6"))

        # EEM4: TTL
        rtio_channels = []
        for i in range(8):
            pads = platform.request("eem4", i)
            phy = ttl_serdes_7series.InOut_8X(pads.p, pads.n)
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))

        # EEM2, EEM3: Urukul
        phy = spi2.SPIMaster(self.platform.request("eem3_spi_p"),
                self.platform.request("eem3_spi_n"))
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=4))

        pads = platform.request("eem3_dds_reset")
        self.specials += DifferentialOutput(0, pads.p, pads.n)

        for signal in "io_update sw0 sw1 sw2 sw3".split():
            pads = platform.request("eem3_{}".format(signal))
            phy = ttl_serdes_7series.Output_8X(pads.p, pads.n)
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))

        # EEM5, EEM6: Zotino
        for i in (5, 6):
            phy = spi2.SPIMaster(self.platform.request("eem{}_spi_p".format(i)),
                    self.platform.request("eem{}_spi_n".format(i)))
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=4))

            for signal in "ldac_n clr_n".split():
                pads = platform.request("eem{}_{}".format(i, signal))
                phy = ttl_serdes_7series.Output_8X(pads.p, pads.n)
                self.submodules += phy
                rtio_channels.append(rtio.Channel.from_phy(phy))

        for i in (1, 2):
            sfp_ctl = platform.request("sfp_ctl", i)
            phy = ttl_simple.Output(sfp_ctl.led)
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))

        self.config["HAS_RTIO_LOG"] = None
        self.config["RTIO_LOG_CHANNEL"] = len(rtio_channels)
        rtio_channels.append(rtio.LogChannel())

        self.add_rtio(rtio_channels)


class _RTIOClockMultiplier(Module):
    def __init__(self, rtio_clk_freq):
        self.clock_domains.cd_rtiox4 = ClockDomain(reset_less=True)

        # See "Global Clock Network Deskew Using Two BUFGs" in ug472.
        clkfbout = Signal()
        clkfbin = Signal()
        rtiox4_clk = Signal()
        self.specials += [
            Instance("MMCME2_BASE",
                p_CLKIN1_PERIOD=1e9/rtio_clk_freq,
                i_CLKIN1=ClockSignal("rtio"),
                i_RST=ResetSignal("rtio"),

                p_CLKFBOUT_MULT_F=8.0, p_DIVCLK_DIVIDE=1,

                o_CLKFBOUT=clkfbout, i_CLKFBIN=clkfbin,

                p_CLKOUT0_DIVIDE_F=2.0, o_CLKOUT0=rtiox4_clk,
            ),
            Instance("BUFG", i_I=clkfbout, o_O=clkfbin),
            Instance("BUFG", i_I=rtiox4_clk, o_O=self.cd_rtiox4.clk)
        ]


class _MasterBase(MiniSoC, AMPSoC):
    mem_map = {
        "cri_con":       0x10000000,
        "rtio":          0x20000000,
        "rtio_dma":      0x30000000,
        "drtio_aux":     0x50000000,
        "mailbox":       0x70000000
    }
    mem_map.update(MiniSoC.mem_map)

    def __init__(self, **kwargs):
        MiniSoC.__init__(self,
                         cpu_type="or1k",
                         sdram_controller_type="minicon",
                         l2_size=128*1024,
                         ident=artiq_version,
                         ethmac_nrxslots=4,
                         ethmac_ntxslots=4,
                         **kwargs)
        AMPSoC.__init__(self)

        platform = self.platform
        rtio_clk_freq = 150e6

        i2c = self.platform.request("i2c")
        self.submodules.i2c = gpio.GPIOTristate([i2c.scl, i2c.sda])
        self.csr_devices.append("i2c")
        self.config["I2C_BUS_COUNT"] = 1
        self.config["HAS_SI5324"] = None
        self.config["SI5324_SOFT_RESET"] = None
        self.config["SI5324_AS_SYNTHESIZER"] = None
        self.config["RTIO_FREQUENCY"] = str(rtio_clk_freq/1e6)

        self.sfp_ctl = [platform.request("sfp_ctl", i) for i in range(1, 3)]
        self.comb += [sc.tx_disable.eq(0) for sc in self.sfp_ctl]
        self.submodules.drtio_transceiver = gtp_7series.GTP(
            qpll_channel=self.drtio_qpll_channel,
            data_pads=[platform.request("sfp", i) for i in range(1, 3)],
            sys_clk_freq=self.clk_freq,
            rtio_clk_freq=rtio_clk_freq)
        self.csr_devices.append("drtio_transceiver")
        self.sync += self.disable_si5324_ibuf.eq(
            ~self.drtio_transceiver.stable_clkin.storage)

        drtio_csr_group = []
        drtio_memory_group = []
        self.drtio_cri = []
        for i in range(2):
            core_name = "drtio" + str(i)
            memory_name = "drtio" + str(i) + "_aux"
            drtio_csr_group.append(core_name)
            drtio_memory_group.append(memory_name)

            core = ClockDomainsRenamer({"rtio_rx": "rtio_rx" + str(i)})(
                DRTIOMaster(self.drtio_transceiver.channels[i]))
            setattr(self.submodules, core_name, core)
            self.drtio_cri.append(core.cri)
            self.csr_devices.append(core_name)

            memory_address = self.mem_map["drtio_aux"] + 0x800*i
            self.add_wb_slave(memory_address, 0x800,
                              core.aux_controller.bus)
            self.add_memory_region(memory_name, memory_address | self.shadow_base, 0x800)
        self.config["HAS_DRTIO"] = None
        self.add_csr_group("drtio", drtio_csr_group)
        self.add_memory_group("drtio_aux", drtio_memory_group)

        rtio_clk_period = 1e9/rtio_clk_freq
        gtp = self.drtio_transceiver.gtps[0]
        platform.add_period_constraint(gtp.txoutclk, rtio_clk_period)
        platform.add_period_constraint(gtp.rxoutclk, rtio_clk_period)
        platform.add_false_path_constraints(
            self.crg.cd_sys.clk,
            gtp.txoutclk, gtp.rxoutclk)
        for gtp in self.drtio_transceiver.gtps[1:]:
            platform.add_period_constraint(gtp.rxoutclk, rtio_clk_period)
            platform.add_false_path_constraints(
                self.crg.cd_sys.clk, gtp.rxoutclk)

        self.submodules.rtio_clkmul = _RTIOClockMultiplier(rtio_clk_freq)
        fix_serdes_timing_path(platform)

    def add_rtio(self, rtio_channels):
        self.submodules.rtio_moninj = rtio.MonInj(rtio_channels)
        self.csr_devices.append("rtio_moninj")

        self.submodules.rtio_core = rtio.Core(rtio_channels, glbl_fine_ts_width=3)
        self.csr_devices.append("rtio_core")

        self.submodules.rtio = rtio.KernelInitiator()
        self.submodules.rtio_dma = ClockDomainsRenamer("sys_kernel")(
            rtio.DMA(self.get_native_sdram_if()))
        self.register_kernel_cpu_csrdevice("rtio")
        self.register_kernel_cpu_csrdevice("rtio_dma")
        self.submodules.cri_con = rtio.CRIInterconnectShared(
            [self.rtio.cri, self.rtio_dma.cri],
            [self.rtio_core.cri] + self.drtio_cri)
        self.register_kernel_cpu_csrdevice("cri_con")

        self.submodules.rtio_analyzer = rtio.Analyzer(self.cri_con.switch.slave,
                                                      self.get_native_sdram_if())
        self.csr_devices.append("rtio_analyzer")

    # Never running out of stupid features, GTs on A7 make you pack
    # unrelated transceiver PLLs into one GTPE2_COMMON yourself.
    def create_qpll(self):
        # The GTP acts up if you send any glitch to its
        # clock input, even while the PLL is held in reset.
        self.disable_si5324_ibuf = Signal(reset=1)
        self.disable_si5324_ibuf.attr.add("no_retiming")
        si5324_clkout = self.platform.request("si5324_clkout")
        si5324_clkout_buf = Signal()
        self.specials += Instance("IBUFDS_GTE2",
            i_CEB=self.disable_si5324_ibuf,
            i_I=si5324_clkout.p, i_IB=si5324_clkout.n,
            o_O=si5324_clkout_buf)
        # Note precisely the rules Xilinx made up:
        # refclksel=0b001 GTREFCLK0 selected
        # refclksel=0b010 GTREFCLK1 selected
        # but if only one clock is used, then it must be 001.
        qpll_drtio_settings = QPLLSettings(
            refclksel=0b001,
            fbdiv=4,
            fbdiv_45=5,
            refclk_div=1)
        qpll_eth_settings = QPLLSettings(
            refclksel=0b010,
            fbdiv=4,
            fbdiv_45=5,
            refclk_div=1)
        qpll = QPLL(si5324_clkout_buf, qpll_drtio_settings,
                    self.crg.clk125_buf, qpll_eth_settings)
        self.submodules += qpll
        self.drtio_qpll_channel, self.ethphy_qpll_channel = qpll.channels


class _SatelliteBase(BaseSoC):
    mem_map = {
        "drtio_aux": 0x50000000,
    }
    mem_map.update(BaseSoC.mem_map)

    def __init__(self, **kwargs):
        BaseSoC.__init__(self,
                 cpu_type="or1k",
                 sdram_controller_type="minicon",
                 l2_size=128*1024,
                 ident=artiq_version,
                 **kwargs)

        platform = self.platform
        rtio_clk_freq = 150e6

        disable_si5324_ibuf = Signal(reset=1)
        disable_si5324_ibuf.attr.add("no_retiming")
        si5324_clkout = platform.request("si5324_clkout")
        si5324_clkout_buf = Signal()
        self.specials += Instance("IBUFDS_GTE2",
            i_CEB=disable_si5324_ibuf,
            i_I=si5324_clkout.p, i_IB=si5324_clkout.n,
            o_O=si5324_clkout_buf)
        qpll_drtio_settings = QPLLSettings(
            refclksel=0b001,
            fbdiv=4,
            fbdiv_45=5,
            refclk_div=1)
        qpll = QPLL(si5324_clkout_buf, qpll_drtio_settings)
        self.submodules += qpll

        self.comb += platform.request("sfp_ctl", 0).tx_disable.eq(0)
        self.submodules.drtio_transceiver = gtp_7series.GTP(
            qpll_channel=qpll.channels[0],
            data_pads=[platform.request("sfp", 0)],
            sys_clk_freq=self.clk_freq,
            rtio_clk_freq=rtio_clk_freq)
        self.csr_devices.append("drtio_transceiver")
        self.sync += disable_si5324_ibuf.eq(
            ~self.drtio_transceiver.stable_clkin.storage)

        self.config["RTIO_FREQUENCY"] = str(rtio_clk_freq/1e6)
        self.submodules.siphaser = SiPhaser7Series(
            si5324_clkin=platform.request("si5324_clkin"),
            si5324_clkout_fabric=platform.request("si5324_clkout_fabric"))
        platform.add_false_path_constraints(
            self.crg.cd_sys.clk, self.siphaser.mmcm_freerun_output)
        self.csr_devices.append("siphaser")
        i2c = self.platform.request("i2c")
        self.submodules.i2c = gpio.GPIOTristate([i2c.scl, i2c.sda])
        self.csr_devices.append("i2c")
        self.config["I2C_BUS_COUNT"] = 1
        self.config["HAS_SI5324"] = None
        self.config["SI5324_SOFT_RESET"] = None

        rtio_clk_period = 1e9/rtio_clk_freq
        gtp = self.drtio_transceiver.gtps[0]
        platform.add_period_constraint(gtp.txoutclk, rtio_clk_period)
        platform.add_period_constraint(gtp.rxoutclk, rtio_clk_period)
        platform.add_false_path_constraints(
            self.crg.cd_sys.clk,
            gtp.txoutclk, gtp.rxoutclk)

        self.submodules.rtio_clkmul = _RTIOClockMultiplier(rtio_clk_freq)
        fix_serdes_timing_path(platform)

    def add_rtio(self, rtio_channels):
        self.submodules.rtio_moninj = rtio.MonInj(rtio_channels)
        self.csr_devices.append("rtio_moninj")

        rx0 = ClockDomainsRenamer({"rtio_rx": "rtio_rx0"})
        self.submodules.rx_synchronizer = rx0(XilinxRXSynchronizer())
        self.submodules.drtio0 = rx0(DRTIOSatellite(
            self.drtio_transceiver.channels[0], rtio_channels,
            self.rx_synchronizer))
        self.csr_devices.append("drtio0")
        self.add_wb_slave(self.mem_map["drtio_aux"], 0x800,
                          self.drtio0.aux_controller.bus)
        self.add_memory_region("drtio0_aux", self.mem_map["drtio_aux"] | self.shadow_base, 0x800)
        self.config["HAS_DRTIO"] = None
        self.add_csr_group("drtio", ["drtio0"])
        self.add_memory_group("drtio_aux", ["drtio0_aux"])


class Master(_MasterBase):
    def __init__(self, *args, **kwargs):
        _MasterBase.__init__(self, *args, **kwargs)

        platform = self.platform
        platform.add_extension(_dio("eem0"))

        rtio_channels = []

        phy = ttl_simple.Output(platform.request("user_led", 0))
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy))
        for sc in self.sfp_ctl:
            phy = ttl_simple.Output(sc.led)
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))

        for i in range(8):
            pads = platform.request("eem0", i)
            phy = ttl_serdes_7series.InOut_8X(pads.p, pads.n)
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))

        self.config["HAS_RTIO_LOG"] = None
        self.config["RTIO_LOG_CHANNEL"] = len(rtio_channels)
        rtio_channels.append(rtio.LogChannel())

        self.add_rtio(rtio_channels)


class Satellite(_SatelliteBase):
    def __init__(self, *args, **kwargs):
        _SatelliteBase.__init__(self, *args, **kwargs)

        platform = self.platform
        platform.add_extension(_dio("eem0"))

        rtio_channels = []
        phy = ttl_simple.Output(platform.request("user_led", 0))
        self.submodules += phy
        rtio_channels.append(rtio.Channel.from_phy(phy))
        for i in range(1, 3):
            phy = ttl_simple.Output(platform.request("sfp_ctl", i).led)
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))

        for i in range(8):
            pads = platform.request("eem0", i)
            phy = ttl_serdes_7series.InOut_8X(pads.p, pads.n)
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))

        self.add_rtio(rtio_channels)


def main():
    parser = argparse.ArgumentParser(
        description="ARTIQ device binary builder for Kasli systems")
    builder_args(parser)
    soc_kasli_args(parser)
    parser.set_defaults(output_dir="artiq_kasli")
    parser.add_argument("-V", "--variant", default="opticlock",
                        help="variant: opticlock/suservo/sysu/mitll/master/satellite "
                             "(default: %(default)s)")
    args = parser.parse_args()

    variant = args.variant.lower()
    if variant == "opticlock":
        cls = Opticlock
    elif variant == "suservo":
        cls = SUServo
    elif variant == "sysu":
        cls = SYSU
    elif variant == "mitll":
        cls = MITLL
    elif variant == "master":
        cls = Master
    elif variant == "satellite":
        cls = Satellite
    else:
        raise SystemExit("Invalid variant (-V/--variant)")

    soc = cls(**soc_kasli_argdict(args))
    build_artiq_soc(soc, builder_argdict(args))


if __name__ == "__main__":
    main()
