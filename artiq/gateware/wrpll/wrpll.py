from migen import *
from migen.genlib.cdc import MultiReg, AsyncResetSynchronizer, PulseSynchronizer
from misoc.interconnect.csr import *
from misoc.interconnect.csr_eventmanager import *

from artiq.gateware.wrpll.ddmtd import DDMTDSampler, DDMTD
from artiq.gateware.wrpll.si549 import Si549

class FrequencyCounter(Module, AutoCSR):
    def __init__(self, domains, counter_width=24):
        self.update = CSR()
        self.busy = CSRStatus()

        counter_reset = Signal()
        counter_stb = Signal()
        timer = Signal(counter_width)

        # # #

        fsm = FSM()
        self.submodules += fsm

        fsm.act("IDLE",
            counter_reset.eq(1),
            If(self.update.re,
                NextValue(timer, 2**counter_width - 1),
                NextState("COUNTING")
            )
        )
        fsm.act("COUNTING",
            self.busy.status.eq(1),
            If(timer != 0,
                NextValue(timer, timer - 1)
            ).Else( 
                counter_stb.eq(1),
                NextState("IDLE")
            )
        )

        for domain in domains:
            name = "counter_" + domain
            counter_csr = CSRStatus(counter_width, name=name)
            setattr(self, name, counter_csr)

            divider = Signal(2)
            divided = Signal()
            divided_sys = Signal()
            divided_sys_r = Signal()
            divided_tick = Signal()
            counter = Signal(counter_width)

            # # #

            sync_domain = getattr(self.sync, domain)
            sync_domain +=[
                divider.eq(divider + 1),
                divided.eq(divider[-1])
            ]
            self.specials += MultiReg(divided, divided_sys)
            self.sync += divided_sys_r.eq(divided_sys)
            self.comb += divided_tick.eq(divided_sys & ~divided_sys_r)

            self.sync += [
                If(counter_stb, counter_csr.status.eq(counter)),
                If(divided_tick, counter.eq(counter + 1)),
                If(counter_reset, counter.eq(0))
            ]

class SkewTester(Module, AutoCSR):
    def __init__(self, rx_synchronizer):
        self.error = CSR()

        # # #
        
        # The RX synchronizer is tested for setup/hold violations by feeding it a
        # toggling pattern and checking that the same toggling pattern comes out.
        toggle_in = Signal()
        self.sync.rtio_rx0 += toggle_in.eq(~toggle_in)
        toggle_out = rx_synchronizer.resync(toggle_in)

        toggle_out_expected = Signal()
        self.sync += toggle_out_expected.eq(~toggle_out)

        error = Signal()
        self.sync += [
            If(toggle_out != toggle_out_expected, error.eq(1)),
            If(self.error.re, error.eq(0))
        ]
        self.specials += MultiReg(error, self.error.w)


class WRPLL(Module, AutoCSR):
    def __init__(self, platform, cd_ref, main_clk_se, COUNTER_BIT=32):
        self.helper_reset = CSRStorage(reset=1)
        self.ref_tag = CSRStatus(COUNTER_BIT)
        self.main_tag = CSRStatus(COUNTER_BIT)

        ddmtd_counter = Signal(COUNTER_BIT)

        ref_tag_sys = Signal(COUNTER_BIT)
        main_tag_sys = Signal(COUNTER_BIT)
        ref_tag_stb_sys = Signal()
        main_tag_stb_sys = Signal()

        # # #

        self.submodules.main_dcxo = Si549(platform.request("ddmtd_main_dcxo_i2c"))
        self.submodules.helper_dcxo = Si549(platform.request("ddmtd_helper_dcxo_i2c"))

        helper_dcxo_pads = platform.request("ddmtd_helper_clk")
        self.clock_domains.cd_helper = ClockDomain()
        self.specials += [
            Instance("IBUFGDS",
                     i_I=helper_dcxo_pads.p, i_IB=helper_dcxo_pads.n,
                     o_O=self.cd_helper.clk),
            AsyncResetSynchronizer(self.cd_helper, self.helper_reset.storage)
        ]

        self.submodules.frequency_counter = FrequencyCounter(["sys", cd_ref.name])

        self.submodules.ddmtd_sampler = DDMTDSampler(cd_ref, main_clk_se)

        self.sync.helper += ddmtd_counter.eq(ddmtd_counter + 1)
        self.submodules.ddmtd_ref = DDMTD(ddmtd_counter, self.ddmtd_sampler.ref_beating)
        self.submodules.ddmtd_main = DDMTD(ddmtd_counter, self.ddmtd_sampler.main_beating)

        # DDMTD tags collection

        self.specials += [
            MultiReg(self.ddmtd_ref.h_tag, ref_tag_sys),
            MultiReg(self.ddmtd_main.h_tag, main_tag_sys)
        ]

        ref_tag_stb_ps = PulseSynchronizer("helper", "sys")
        main_tag_stb_ps = PulseSynchronizer("helper", "sys")
        self.submodules += [
            ref_tag_stb_ps,
            main_tag_stb_ps
        ]
        self.sync.helper += [
            ref_tag_stb_ps.i.eq(self.ddmtd_ref.h_tag_update),
            main_tag_stb_ps.i.eq(self.ddmtd_main.h_tag_update)
        ]
        self.sync += [
            ref_tag_stb_sys.eq(ref_tag_stb_ps.o),
            main_tag_stb_sys.eq(main_tag_stb_ps.o)
        ]

        self.sync += [
            If(ref_tag_stb_sys,
                self.ref_tag.status.eq(ref_tag_sys),
            ),
            If(main_tag_stb_sys,
                self.main_tag.status.eq(main_tag_sys)
            )
        ]

        # EventMangers for firmware interrupt

        self.submodules.ref_tag_ev = EventManager()
        self.ref_tag_ev.stb = EventSourcePulse()
        self.ref_tag_ev.finalize()

        self.submodules.main_tag_ev = EventManager()
        self.main_tag_ev.stb = EventSourcePulse()
        self.main_tag_ev.finalize()

        self.sync += [
            self.ref_tag_ev.stb.trigger.eq(ref_tag_stb_sys),
            self.main_tag_ev.stb.trigger.eq(main_tag_stb_sys)
        ]

        self.submodules.ev = SharedIRQ(self.ref_tag_ev, self.main_tag_ev)

class FrequencyMultiplier(Module, AutoCSR):
    def __init__(self, clkin):
        clkin_se = Signal()
        mmcm_locked = Signal()
        mmcm_fb_clk = Signal()
        ref_clk = Signal()
        self.clock_domains.cd_ref = ClockDomain()
        self.refclk_reset = CSRStorage(reset=1)

        self.mmcm_bypass = CSRStorage()
        self.mmcm_locked = CSRStatus()
        self.mmcm_reset = CSRStorage(reset=1)

        self.mmcm_daddr = CSRStorage(7)
        self.mmcm_din = CSRStorage(16)
        self.mmcm_dwen = CSRStorage()
        self.mmcm_den = CSRStorage()
        self.mmcm_dclk = CSRStorage()
        self.mmcm_dout = CSRStatus(16)
        self.mmcm_dready = CSRStatus()

        # # #

        self.specials += [
            Instance("IBUFDS",
                i_I=clkin.p, i_IB=clkin.n,
                o_O=clkin_se),
            # MMCME2 is capable to accept 10MHz input while PLLE2 only support down to 19MHz input (DS191)
            # The MMCME2 can be reconfiged during runtime using the Dynamic Reconfiguration Ports
            Instance("MMCME2_ADV",
                p_BANDWIDTH="HIGH",  # lower output jitter (see https://support.xilinx.com/s/question/0D52E00006iHqRqSAK)
                o_LOCKED=self.mmcm_locked.status,
                i_RST=self.mmcm_reset.storage,
                
                p_CLKIN1_PERIOD=8, # ns
                i_CLKIN1=clkin_se,
                i_CLKINSEL=1,  # 1=CLKIN1 0=CLKIN2

                # VCO @ 1.25GHz 
                p_CLKFBOUT_MULT_F=10, p_DIVCLK_DIVIDE=1,
                i_CLKFBIN=mmcm_fb_clk, o_CLKFBOUT=mmcm_fb_clk, 

                # 125MHz for WRPLL
                p_CLKOUT0_DIVIDE_F=10, p_CLKOUT0_PHASE=0.0, o_CLKOUT0=ref_clk,

                # Dynamic Reconfiguration Ports
                i_DADDR = self.mmcm_daddr.storage,
                i_DI = self.mmcm_din.storage,
                i_DWE = self.mmcm_dwen.storage,
                i_DEN = self.mmcm_den.storage,
                i_DCLK = self.mmcm_dclk.storage,
                o_DO = self.mmcm_dout.status,
                o_DRDY = self.mmcm_dready.status
            ),
            Instance("BUFGMUX",
                i_I0=ref_clk,
                i_I1=clkin_se,
                i_S=self.mmcm_bypass.storage,
                o_O=self.cd_ref.clk
            ),
            AsyncResetSynchronizer(self.cd_ref, self.refclk_reset.storage),
        ]
