import argparse

from migen import *
from migen.build.generic_platform import *
from misoc.cores.i2c import *
from misoc.cores.sequencer import *
from misoc.integration.builder import *
from misoc.integration.soc_core import mem_decoder
from misoc.targets.kc705 import BaseSoC, soc_kc705_args, soc_kc705_argdict

from artiq.gateware.ad9154_fmc_ebz import ad9154_fmc_ebz
from artiq.gateware import rtio
from artiq.gateware.rtio.phy import ttl_simple
from artiq.gateware.drtio.transceiver import gtx_7series
from artiq.gateware.drtio import DRTIOSatellite
from artiq import __version__ as artiq_version


# TODO: parameters for sawg_3g
# TODO: move I2C programming to softcore CPU
def get_i2c_program(sys_clk_freq):
    # NOTE: the logical parameters DO NOT MAP to physical values written
    # into registers. They have to be mapped; see the datasheet.
    # DSPLLsim reports the logical parameters in the design summary, not
    # the physical register values (but those are present separately).
    N1_HS  = 6     # 10
    NC1_LS = 7     # 8
    N2_HS  = 6     # 10
    N2_LS  = 20111 # 20112
    N31    = 2513  # 2514
    N32    = 4596  # 4597

    i2c_sequence = [
        # PCA9548: select channel 7
        [(0x74 << 1), 1 << 7],
        # Si5324: configure
        [(0x68 << 1), 0,   0b01010000],        # FREE_RUN=1
        [(0x68 << 1), 1,   0b11100100],        # CK_PRIOR2=1 CK_PRIOR1=0
        [(0x68 << 1), 2,   0b0010 | (4 << 4)], # BWSEL=4
        [(0x68 << 1), 3,   0b0101 | 0x10],     # SQ_ICAL=1
        [(0x68 << 1), 4,   0b10010010],        # AUTOSEL_REG=b10
        [(0x68 << 1), 6,            0x07],     # SFOUT1_REG=b111
        [(0x68 << 1), 25,  (N1_HS  << 5 ) & 0xff],
        [(0x68 << 1), 31,  (NC1_LS >> 16) & 0xff],
        [(0x68 << 1), 32,  (NC1_LS >> 8 ) & 0xff],
        [(0x68 << 1), 33,  (NC1_LS)       & 0xff],
        [(0x68 << 1), 40,  (N2_HS  << 5 ) & 0xff |
                           (N2_LS  >> 16) & 0xff],
        [(0x68 << 1), 41,  (N2_LS  >> 8 ) & 0xff],
        [(0x68 << 1), 42,  (N2_LS)        & 0xff],
        [(0x68 << 1), 43,  (N31    >> 16) & 0xff],
        [(0x68 << 1), 44,  (N31    >> 8)  & 0xff],
        [(0x68 << 1), 45,  (N31)          & 0xff],
        [(0x68 << 1), 46,  (N32    >> 16) & 0xff],
        [(0x68 << 1), 47,  (N32    >> 8)  & 0xff],
        [(0x68 << 1), 48,  (N32)          & 0xff],
        [(0x68 << 1), 137,          0x01],     # FASTLOCK=1
        [(0x68 << 1), 136,          0x40],     # ICAL=1
    ]

    program = [
        InstWrite(I2C_CONFIG_ADDR, int(sys_clk_freq/1e3)),
    ]
    for subseq in i2c_sequence:
        program += [
            InstWrite(I2C_XFER_ADDR, I2C_START),
            InstWait(I2C_XFER_ADDR, I2C_IDLE),
        ]
        for octet in subseq:
            program += [
                InstWrite(I2C_XFER_ADDR, I2C_WRITE | octet),
                InstWait(I2C_XFER_ADDR, I2C_IDLE),
            ]
        program += [
            InstWrite(I2C_XFER_ADDR, I2C_STOP),
            InstWait(I2C_XFER_ADDR, I2C_IDLE),
        ]
    program += [
        InstEnd(),
    ]
    return program


class Si5324ResetClock(Module):
    def __init__(self, platform, sys_clk_freq):
        self.si5324_not_ready = Signal(reset=1)

        # minimum reset pulse 1us
        reset_done = Signal()
        si5324_rst_n = platform.request("si5324").rst_n
        reset_val = int(sys_clk_freq*1.1e-6)
        reset_ctr = Signal(max=reset_val+1, reset=reset_val)
        self.sync += \
            If(reset_ctr != 0,
                reset_ctr.eq(reset_ctr - 1)
            ).Else(
                si5324_rst_n.eq(1),
                reset_done.eq(1)
            )
        # 10ms after reset to microprocessor access ready
        ready_val = int(sys_clk_freq*11e-3)
        ready_ctr = Signal(max=ready_val+1, reset=ready_val)
        self.sync += \
            If(reset_done,
                If(ready_ctr != 0,
                    ready_ctr.eq(ready_ctr - 1)
                ).Else(
                    self.si5324_not_ready.eq(0)
                )
            )

        si5324_clkin = platform.request("si5324_clkin")
        self.specials += \
            Instance("OBUFDS",
                i_I=ClockSignal("rtio_rx"),
                o_O=si5324_clkin.p, o_OB=si5324_clkin.n
            )


class Satellite(BaseSoC):
    mem_map = {
        "drtio_aux": 0x50000000,
    }
    mem_map.update(BaseSoC.mem_map)

    def __init__(self, cfg, medium, **kwargs):
        BaseSoC.__init__(self,
                 cpu_type="or1k",
                 sdram_controller_type="minicon",
                 l2_size=128*1024,
                 ident=artiq_version,
                 **kwargs)

        platform = self.platform

        rtio_channels = []
        for i in range(8):
            phy = ttl_simple.Output(platform.request("user_led", i))
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))
        for sma in "user_sma_gpio_p", "user_sma_gpio_n":
            phy = ttl_simple.Inout(platform.request(sma))
            self.submodules += phy
            rtio_channels.append(rtio.Channel.from_phy(phy))

        i2c_master = I2CMaster(platform.request("i2c"))
        sequencer = ResetInserter()(Sequencer(get_i2c_program(self.clk_freq)))
        si5324_reset_clock = Si5324ResetClock(platform, self.clk_freq)
        self.submodules += i2c_master, sequencer, si5324_reset_clock
        self.comb += [
            sequencer.bus.connect(i2c_master.bus),
            sequencer.reset.eq(si5324_reset_clock.si5324_not_ready)
        ]

        if medium == "sfp":
            self.comb += platform.request("sfp_tx_disable_n").eq(1)
            tx_pads = platform.request("sfp_tx")
            rx_pads = platform.request("sfp_rx")
        elif medium == "sma":
            tx_pads = platform.request("user_sma_mgt_tx")
            rx_pads = platform.request("user_sma_mgt_rx")
        else:
            raise ValueError

        if cfg == "simple_gbe":
            # GTX_1000BASE_BX10 Ethernet compatible, 62.5MHz RTIO clock
            # simple TTLs
            self.submodules.transceiver = gtx_7series.GTX_1000BASE_BX10(
                clock_pads=platform.request("sgmii_clock"),
                tx_pads=tx_pads,
                rx_pads=rx_pads,
                sys_clk_freq=self.clk_freq,
                clock_div2=True)
        elif cfg == "sawg_3g":
            # 3Gb link, 150MHz RTIO clock
            # with SAWG on local RTIO and AD9154-FMC-EBZ
            platform.register_extension(ad9154_fmc_ebz)
            self.submodules.transceiver = gtx_7series.GTX_3G(
                clock_pads=platform.request("ad9154_refclk"),
                tx_pads=tx_pads,
                rx_pads=rx_pads,
                sys_clk_freq=self.clk_freq)
        else:
            raise ValueError
        self.submodules.rx_synchronizer = gtx_7series.RXSynchronizer(
            self.transceiver.rtio_clk_freq, initial_phase=180.0)
        self.submodules.drtio = DRTIOSatellite(
            self.transceiver, rtio_channels, self.rx_synchronizer)
        self.csr_devices.append("rx_synchronizer")
        self.csr_devices.append("drtio")
        self.add_wb_slave(mem_decoder(self.mem_map["drtio_aux"]),
                          self.drtio.aux_controller.bus)
        self.add_memory_region("drtio_aux", self.mem_map["drtio_aux"] | self.shadow_base, 0x800)

        rtio_clk_period = 1e9/self.transceiver.rtio_clk_freq
        platform.add_period_constraint(self.transceiver.txoutclk, rtio_clk_period)
        platform.add_period_constraint(self.transceiver.rxoutclk, rtio_clk_period)
        platform.add_false_path_constraints(
            platform.lookup_request("clk200"),
            self.transceiver.txoutclk, self.transceiver.rxoutclk)


def main():
    parser = argparse.ArgumentParser(
        description="ARTIQ device binary builder / KC705 DRTIO satellite")
    builder_args(parser)
    soc_kc705_args(parser)
    parser.add_argument("-c", "--config", default="simple_gbe",
                        help="configuration: simple_gbe/sawg_3g "
                             "(default: %(default)s)")
    parser.add_argument("--medium", default="sfp",
                        help="medium to use for transceiver link: sfp/sma "
                             "(default: %(default)s)")
    args = parser.parse_args()

    soc = Satellite(args.config, args.medium, **soc_kc705_argdict(args))
    builder = Builder(soc, **builder_argdict(args))
    builder.build()


if __name__ == "__main__":
    main()
