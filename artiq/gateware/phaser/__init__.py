from migen import *
from misoc.cores.duc import complex

from artiq.gateware.phaser.dac_phy import DAC34H84PHY, DAC_DATA_WIDTH
from artiq.gateware.phaser.dds import MultiToneDDS
from artiq.gateware.phaser.register import RO, RW, AddressDecoder
from artiq.gateware.rtio import rtlink

from collections import namedtuple

Phy = namedtuple("Phy", "rtlink probes overrides")

PHASER_GW_VARIANT_MTDDS = 1


class PhaserMTDDS(Module):
    def __init__(
        self,
        hw_variant_pins,
        att_rstn_pins,
        trf_ctrl_pins,
        dac_data_pins,
        dac_ctrl_pins,
        dds_tones,
        dds_sample_per_cycle,
        use_pipeline_adder,
        f_width=32,
        p_width=16,
        a_width=16,
    ):

        # Multitone DAC
        self.submodules.dac_phy = dac_phy = DAC34H84PHY(
            dac_data_pins, dac_ctrl_pins, dds_sample_per_cycle
        )
        dac_iq_sinks = [
            [dac_phy.sinks_a, dac_phy.sinks_b],
            [dac_phy.sinks_c, dac_phy.sinks_d],
        ]

        # 0: test_word -> PHY
        # 1: DDS -> PHY
        # 2-3: reserved
        dac_source_sel = [Signal(2) for _ in range(len(dac_iq_sinks))]
        test_words = [Record(complex(DAC_DATA_WIDTH)) for _ in range(len(dac_iq_sinks))]
        cfg_regs = [
            (hw_variant_pins, RO),
            (C(PHASER_GW_VARIANT_MTDDS), RO),
            (C(dds_sample_per_cycle), RO),
            (C(dds_tones), RO),
            (Cat(dac_phy.en, dac_phy.reset_n, dac_phy.sleep), RW),
            (dac_phy.alarm, RO),
            (Cat(dac_source_sel[0], dac_source_sel[1]), RW),
            (test_words[0].i, RW),
            (test_words[0].q, RW),
            (test_words[1].i, RW),
            (test_words[1].q, RW),
            (Cat(att_rstn_pins[0], att_rstn_pins[1]), RW),
            (Cat(trf_ctrl_pins[0].ps, trf_ctrl_pins[1].ps), RW),
            (Cat(trf_ctrl_pins[0].ld, trf_ctrl_pins[1].ld), RO),
        ]

        reg_banks = [cfg_regs]
        cdr = ClockDomainsRenamer("rio")
        for ch, iq_ch in enumerate(dac_iq_sinks):
            dds = cdr(
                MultiToneDDS(
                    dds_sample_per_cycle,
                    dds_tones,
                    f_width,
                    p_width,
                    a_width,
                    DAC_DATA_WIDTH,
                    use_pipeline_adder,
                )
            )
            reg_banks.extend(dds.reg_banks)
            self.submodules += dds

            for sink_i, sink_q, source in zip(*iq_ch, dds.sources):
                cases = {
                    0: [
                        sink_i.eq(test_words[ch].i),
                        sink_q.eq(test_words[ch].q),
                    ],
                    1: [
                        sink_i.eq(source.i),
                        sink_q.eq(source.q),
                    ],
                }
                self.sync.rio += Case(dac_source_sel[ch], cases)

        self.phys = []
        for reg in reg_banks:
            decoder = cdr(AddressDecoder(reg))
            self.submodules += decoder

            if decoder.source is not None:
                rt_i = rtlink.IInterface(data_width=len(decoder.source.data), timestamped=False)
            else:
                rt_i = None
            rt_interface = rtlink.Interface(
                rtlink.OInterface(
                    data_width=len(decoder.sink.data),
                    address_width=len(decoder.sink.address),
                    enable_replace=False,
                ),
                rt_i,
            )
            # connect register decoder to rtlink
            self.comb += [
                decoder.sink.stb.eq(rt_interface.o.stb),
                decoder.sink.address.eq(rt_interface.o.address),
                decoder.sink.data.eq(rt_interface.o.data),
            ]
            if rt_interface.i is not None:
                self.comb += [
                    rt_interface.i.stb.eq(decoder.source.stb),
                    rt_interface.i.data.eq(decoder.source.data),
                ]

            self.phys.append(Phy(rt_interface, [], []))
