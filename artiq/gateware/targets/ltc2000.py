from artiq.gateware import rtio
from migen import *
from misoc.interconnect.csr import AutoCSR, CSRStorage
from misoc.interconnect.stream import Endpoint
from artiq.gateware.ltc2000phy import Ltc2000phy
from artiq.gateware.rtio import rtlink
from misoc.cores.duc import PhasedAccu, CosSinGen, saturate
from collections import namedtuple
from .sumandscale import SumAndScale

class PolyphaseDDS(Module):
    """Composite DDS with sub-DDSs synthesizing
       individual phases to increase fmax.
    """
    def __init__(self, n, fwidth, pwidth, z=18, x=15, zl=9, xd=4, backoff=None, share_lut=None):
        self.ftw  = Signal(fwidth)
        self.ptw  = Signal(pwidth)
        self.clr  = Signal()
        self.dout = Signal((x+1)*n)

        ###

        paccu = PhasedAccu(n, fwidth, pwidth)
        self.comb += paccu.clr.eq(self.clr)
        self.comb += paccu.f.eq(self.ftw)
        self.comb += paccu.p.eq(self.ptw)
        self.submodules.paccu = paccu
        ddss = [CosSinGen() for i in range(n)]
        for idx, dds in enumerate(ddss):
            self.submodules += dds
            self.comb += dds.z.eq(paccu.z[idx])
            self.comb += self.dout[idx*16:(idx+1)*16].eq(dds.y)

class DoubleDataRateDDS(Module):
    """Composite DDS running at twice the system clock rate.
    """
    def __init__(self, n, fwidth, pwidth, z=18, x=15, zl=9, xd=4, backoff=None, share_lut=None):
        self.ftw  = Signal(fwidth)
        self.ptw  = Signal(pwidth)
        self.clr  = Signal()
        self.dout = Signal((x+1)*n*2)

        ###

        paccu = ClockDomainsRenamer("sys2x")(PhasedAccu(n, fwidth, pwidth)) # Running this at 2x clock speed
        self.comb += [
            paccu.clr.eq(self.clr),
            paccu.f.eq(self.ftw),
            paccu.p.eq(self.ptw),
        ]
        self.submodules.paccu = paccu
        self.ddss = [ClockDomainsRenamer("sys2x")(CosSinGen()) for _ in range(n)]
        counter = Signal()
        dout2x = Signal((x+1)*n*2)  # output data modified in 2x domain
        for idx, dds in enumerate(self.ddss):
            setattr(self.submodules, f"dds{idx}", dds)
            self.comb += dds.z.eq(paccu.z[idx])

            self.sync.sys2x += [
                If(counter,
                    dout2x[idx*16:(idx+1)*16].eq(dds.x)
                ).Else(
                    dout2x[(idx+n)*16:(idx+n+1)*16].eq(dds.x)
                ),
                counter.eq(~counter)
            ]
        self.sync += [
            If(~counter,
                # Output the full dout array in sys domain
                self.dout.eq(dout2x)
            )
        ]


class LTC2000DDSModule(Module, AutoCSR):
    """The line data is interpreted as:

        * 16 bit amplitude offset
        * 32 bit amplitude first order derivative
        * 48 bit amplitude second order derivative
        * 48 bit amplitude third order derivative
        * 16 bit phase offset
        * 32 bit frequency word
        * 32 bit chirp
    """

    def __init__(self):
        NPHASES = 12
        self.clear = Signal()
        self.ftw = Signal(32)
        self.atw = Signal(32)
        self.ptw = Signal(18)
        self.amplitude = Signal(16)
        self.gain = Signal(16)

        self.shift = Signal(4)
        self.shift_counter = Signal(16) # Need to count to 2**shift - 1
        self.shift_stb = Signal()

        phase_msb_word = Signal(16)      # Upper 16 bits of 18-bit phase value
        control_word = Signal(16)        # Packed: shift[3:0] + phase_lsb[5:4] + reserved[15:6]
        reconstructed_phase = Signal(18)

        self.reserved = Signal(12) # for future use

        self.i = Endpoint([("data", 240)])

        self.comb += [
            self.shift_stb.eq((self.shift == 0) |
                             (self.shift_counter == (1 << self.shift) - 1)) # power of two for strobing
        ]
        self.sync += [
            If(self.shift == 0,
                self.shift_counter.eq(0)
            ).Elif(self.shift_counter == (1 << self.shift) - 1,
                self.shift_counter.eq(0)
            ).Else(
                self.shift_counter.eq(self.shift_counter + 1)
            )
        ]

        z = [Signal(32) for i in range(3)] # phase, dphase, ddphase
        x = [Signal(48) for i in range(4)] # amp, damp, ddamp, dddamp

        self.sync += [
            self.ftw.eq(z[1]),
            self.atw.eq(x[0]),
            self.ptw.eq(reconstructed_phase),

            # Using shift here as a divider
            If(self.shift_stb,
                x[0].eq(x[0] + x[1]),
                x[1].eq(x[1] + x[2]),
                x[2].eq(x[2] + x[3]),
                z[1].eq(z[1] + z[2]),
            ),

            If(self.i.stb,
                x[0].eq(0),
                x[1].eq(0),
                Cat(x[0][32:],           # amp offset (16 bits) - Word 0
                    x[1][16:],           # damp (32 bits) - Words 1-2
                    x[2],                # ddamp (48 bits) - Words 3-5
                    x[3],                # dddamp (48 bits) - Words 6-8
                    phase_msb_word,      # phase main (16 bits) - Word 9
                    z[1],                # ftw (32 bits) - Words 10-11
                    z[2],                # chirp (32 bits) - Words 12-13
                    control_word,        # control word (16 bits) - Word 14
                ).eq(self.i.payload.raw_bits()),
                self.shift_counter.eq(0),
            )
        ]

        self.comb += [
            # Reconstruct 18-bit phase with extension bits in correct position
            reconstructed_phase.eq(Cat(
                control_word[5],
                control_word[4],                # Phase extension bits [5:4] become LSBs [1:0]
                phase_msb_word                  # Main phase bits become MSBs [17:2]
            )),

            self.shift.eq(Cat(
                control_word[3],
                control_word[2],
                control_word[1],
                control_word[0]
            )),   # Shift value in bits [3:0]

            self.amplitude.eq(x[0][32:])
        ]

        self.submodules.dds = DoubleDataRateDDS(NPHASES, 32, 18) # 12 phases at 200 MHz => 2400 MSPS, output updated at 100 MHz
        self.comb += [
            self.dds.ftw.eq(self.ftw),
            self.dds.ptw.eq(self.ptw),
            self.dds.clr.eq(self.clear)
        ]


class LTC2000DataSynth(Module, AutoCSR):
    def __init__(self, NUM_OF_DDS, NPHASES):
        self.amplitudes = Array([[Signal(16, name=f"amplitudes_{i}_{j}") for i in range(NPHASES)] for j in range(NUM_OF_DDS)])
        self.data_in = Array([[Signal(16, name=f"data_in_{i}_{j}") for i in range(NPHASES)] for j in range(NUM_OF_DDS)])
        self.ios = []

        self.summers = [SumAndScale() for _ in range(NPHASES)]
        for idx, summer in enumerate(self.summers):
            setattr(self.submodules, f"summer{idx}", summer)

        for i in range(NPHASES):
            for j in range(NUM_OF_DDS):
                self.ios.append(self.amplitudes[j][i])
                self.ios.append(self.data_in[j][i])
                self.comb += [
                    self.summers[i].inputs[j].eq(self.data_in[j][i]),
                    self.summers[i].amplitudes[j].eq(self.amplitudes[j][i]),
                ]

Phy = namedtuple("Phy", "rtlink probes overrides name")

class LTC2000(Module, AutoCSR):

    def __init__(self, platform, ltc2000_pads):
        NUM_OF_DDS = 4
        NPHASES = 24

        self.submodules.ltc2000datasynth = LTC2000DataSynth(NUM_OF_DDS, NPHASES)

        self.tones = [LTC2000DDSModule() for _ in range(NUM_OF_DDS)]
        for idx, tone in enumerate(self.tones):
            setattr(self.submodules, f"tone{idx}", tone)

        self.phys = []

        platform.add_extension(ltc2000_pads)
        self.dac_pads = platform.request("ltc2000")
        self.submodules.ltc2000 = Ltc2000phy(self.dac_pads)

        clear = Signal(NUM_OF_DDS)
        reset = Signal()
        trigger = Signal(NUM_OF_DDS)
        self.comb += self.ltc2000.reset.eq(reset)

        gain_iface = rtlink.Interface(rtlink.OInterface(
            data_width=16,
            address_width=4,
            enable_replace=False
        ))

        tone_gains = Array([tone.gain for tone in self.tones])
        self.sync.rio += [
            If(gain_iface.o.stb,
                tone_gains[gain_iface.o.address].eq(gain_iface.o.data)
            )
        ]

        clear_iface = rtlink.Interface(rtlink.OInterface(
            data_width=NUM_OF_DDS,
            enable_replace=False
        ))

        self.sync.rio += [
            If(clear_iface.o.stb,
                clear.eq(clear_iface.o.data)
            )
        ]

        trigger_iface = rtlink.Interface(rtlink.OInterface(
            data_width=NUM_OF_DDS,
            enable_replace=False))

        self.sync.rio += [
            If(trigger_iface.o.stb,
                trigger.eq(trigger_iface.o.data)
            )
        ]

        reset_iface = rtlink.Interface(rtlink.OInterface(
            data_width=1,
            enable_replace=False))

        self.sync.rio += [
            If(reset_iface.o.stb,
                reset.eq(reset_iface.o.data)
            )
        ]

        for idx, tone in enumerate(self.tones):
            self.comb += [
                tone.clear.eq(clear[idx]),
            ]

            rtl_iface = rtlink.Interface(rtlink.OInterface(
                data_width=16, address_width=4))

            array = Array(tone.i.data[wi: wi+16] for wi in range(0, len(tone.i.data), 16))

            self.sync.rio += [
                tone.i.stb.eq(trigger_iface.o.data[idx] & trigger_iface.o.stb),
                If(rtl_iface.o.stb,
                    array[rtl_iface.o.address].eq(rtl_iface.o.data),
                ),
            ]

            self.phys.append(Phy(rtl_iface, [], [], 'rtl_iface'))

        for i in range(NPHASES):
            for j in range(NUM_OF_DDS):
                self.comb += self.ltc2000datasynth.data_in[j][i].eq(self.tones[j].dds.dout[i*16:(i+1)*16])
                self.comb += self.ltc2000datasynth.amplitudes[j][i].eq(self.tones[j].amplitude)

        for i in range(NPHASES):
            self.sync += self.ltc2000.data[i*16:(i+1)*16].eq(self.ltc2000datasynth.summers[i].output)

        self.phys.append(Phy(trigger_iface, [], [], 'trigger_iface'))
        self.phys.append(Phy(clear_iface, [], [], 'clear_iface'))
        self.phys.append(Phy(reset_iface, [], [], 'reset_iface'))
        self.phys.append(Phy(gain_iface, [], [], 'gain_iface'))

import json
import csv
import os
from migen.sim import Simulator
from migen import *
from misoc.interconnect.stream import Endpoint

class LTC2000DDSModuleTest(Module):
    """We're ONLY tests coefficient processing - no DDS"""

    def __init__(self):
        self.clear = Signal()
        self.ftw = Signal(32)
        self.atw = Signal(32)
        self.ptw = Signal(18)
        self.amplitude = Signal(16)
        self.gain = Signal(16)
        self.shift = Signal(4)
        self.shift_counter = Signal(16)
        self.shift_stb = Signal()
        self.reserved = Signal(12)

        phase_msb_word = Signal(16)      # Upper 16 bits of 18-bit phase value
        control_word = Signal(16)        # Packed: shift[3:0] + phase_lsb[5:4] + reserved[15:6]
        reconstructed_phase = Signal(18)  # The full 18-bit phase value

        self.i = Endpoint([("data", 240)])

        self.comb += [
            self.shift_stb.eq((self.shift == 0) |
                             (self.shift_counter == (1 << self.shift) - 1))
        ]
        self.sync += [
            If(self.shift == 0,
                self.shift_counter.eq(0)
            ).Elif(self.shift_counter == (1 << self.shift) - 1,
                self.shift_counter.eq(0)
            ).Else(
                self.shift_counter.eq(self.shift_counter + 1)
            )
        ]

        z = [Signal(32) for i in range(3)]  # phase, dphase, ddphase
        x = [Signal(48) for i in range(4)]  # amp, damp, ddamp, dddamp

        self.z = z
        self.x = x

        self.phase_msb_word = phase_msb_word
        self.control_word = control_word
        self.reconstructed_phase = reconstructed_phase

        self.sync += [
            self.ftw.eq(z[1]),
            self.atw.eq(x[0]),
            self.ptw.eq(reconstructed_phase),

            If(self.shift_stb,
                x[0].eq(x[0] + x[1]),
                x[1].eq(x[1] + x[2]),
                x[2].eq(x[2] + x[3]),
                z[1].eq(z[1] + z[2]),
            ),

            If(self.i.stb,
                x[0].eq(0),
                x[1].eq(0),
                Cat(x[0][32:],           # amp offset (16 bits) - Word 0
                    x[1][16:],           # damp (32 bits) - Words 1-2
                    x[2],                # ddamp (48 bits) - Words 3-5
                    x[3],                # dddamp (48 bits) - Words 6-8
                    phase_msb_word,      # phase main (16 bits) - Word 9
                    z[1],                # ftw (32 bits) - Words 10-11
                    z[2],                # chirp (32 bits) - Words 12-13
                    control_word,        # control word (16 bits) - Word 14
                ).eq(self.i.payload.raw_bits()),
                self.shift_counter.eq(0),
            )
        ]

        self.comb += [
            reconstructed_phase.eq(Cat(
                control_word[4],
                control_word[5],
                phase_msb_word
            )),

            self.shift.eq(Cat(
                control_word[0],
                control_word[1],
                control_word[2],
                control_word[3]
            )),

            self.amplitude.eq(x[0][32:])
        ]

class TestConfiguration:
    """Class to handle test configuration loading"""

    def __init__(self, config_dict):
        self.name = config_dict.get('name', 'Unnamed Test')
        self.description = config_dict.get('description', '')
        self.cycles = config_dict.get('cycles', 100)
        self.shift = config_dict.get('shift', 0)
        self.coefficients = config_dict.get('coefficients', {})
        self.output_options = config_dict.get('output', {})
        self.validation = config_dict.get('validation', {})

        default_coeffs = {
            'amp': 0,
            'damp': 0,
            'ddamp': 0,
            'dddamp': 0,
            'phase_offset': 0,
            'ftw': 0,
            'chirp': 0,
            'reserved': 0
        }
        default_coeffs.update(self.coefficients)
        self.coefficients = default_coeffs

    def get_update_interval(self):
        return 1 if self.shift == 0 else (1 << self.shift)

    def pack_coefficients(self):
        """Pack coefficients into the format expected by the module (240-bit format)"""
        phase_value = self.coefficients['phase_offset']
        if phase_value >= (1 << 18) or phase_value < 0:
            raise ValueError(f"Phase value {phase_value} exceeds 18-bit range [0, {(1<<18)-1}]")

        phase_msb = (phase_value >> 2) & 0xFFFF   # Upper 16 bits of 18-bit phase value
        phase_lsb = phase_value & 0x3             # Bottom 2 bits of 18-bit phase value

        return (
            self.coefficients['amp'] |                          # bits [15:0] (16 bits)
            (self.coefficients['damp'] << 16) |                 # bits [47:16] (32 bits)
            (self.coefficients['ddamp'] << 48) |                # bits [95:48] (48 bits)
            (self.coefficients['dddamp'] << 96) |               # bits [143:96] (48 bits)
            (phase_msb << 144) |                               # bits [159:144] (16 bits)
            (self.coefficients['ftw'] << 160) |                 # bits [191:160] (32 bits)
            (self.coefficients['chirp'] << 192) |               # bits [223:192] (32 bits)
            (self.shift << 224) |                               # bits [227:224] (4 bits)
            (phase_lsb << 228)                                  # bits [229:228] (2 bits)
        )

class TestResult:
    """Class to store and analyze test results"""

    def __init__(self, config):
        self.config = config
        self.cycles = []
        self.amplitudes = []
        self.updates = []
        self.debug_info = []
        self.full_cycles = []
        self.full_updates = []
        self.passed = None
        self.errors = []

    def add_sample(self, cycle, amplitude, updated, debug_info=None):
        self.cycles.append(cycle)
        self.amplitudes.append(amplitude)
        self.updates.append(updated)
        self.debug_info.append(debug_info or {})

    def add_full_cycle_data(self, cycle, updated):
        """Add full cycle data for validation purposes"""
        self.full_cycles.append(cycle)
        self.full_updates.append(updated)

    def validate(self):
        """Validate results against expected behavior"""
        self.passed = True
        self.errors = []

        validation = self.config.validation

        if 'final_amplitude' in validation:
            expected = validation['final_amplitude']
            actual = self.amplitudes[-1] if self.amplitudes else 0
            tolerance = validation.get('amplitude_tolerance', 0)

            if abs(actual - expected) > tolerance:
                self.passed = False
                self.errors.append(f"Final amplitude {actual} != expected {expected} (tolerance: {tolerance})")

        if 'final_ptw' in validation:
            expected_ptw = validation['final_ptw']
            actual_ptw = None

            for i in reversed(range(len(self.debug_info))):
                debug_info = self.debug_info[i]
                if debug_info and 'ptw' in debug_info:
                    actual_ptw = debug_info['ptw']
                    break  # Take the most recent PTW value

            if actual_ptw is not None:
                tolerance = validation.get('ptw_tolerance', 0)
                if abs(actual_ptw - expected_ptw) > tolerance:
                    self.passed = False
                    self.errors.append(f"Final PTW {actual_ptw} != expected {expected_ptw} (tolerance: {tolerance})")
            else:
                self.passed = False
                self.errors.append("Could not retrieve PTW value for validation")

        if 'check_updates' in validation and validation['check_updates']:
            expected_interval = self.config.get_update_interval()

            if self.full_cycles and self.full_updates:
                update_cycles = [self.full_cycles[i] for i, updated in enumerate(self.full_updates) if updated]
            else:
                update_cycles = [self.cycles[i] for i, updated in enumerate(self.updates) if updated]

            for i in range(1, len(update_cycles)):
                actual_interval = update_cycles[i] - update_cycles[i-1]
                if actual_interval != expected_interval:
                    self.passed = False
                    self.errors.append(f"Update interval {actual_interval} != expected {expected_interval} at cycle {update_cycles[i]}")
                    break

        if 'monotonic' in validation:
            direction = validation['monotonic']  # 'increasing', 'decreasing', 'non_decreasing', 'non_increasing'
            for i in range(1, len(self.amplitudes)):
                if direction == 'increasing' and self.amplitudes[i] < self.amplitudes[i-1]:
                    self.passed = False
                    self.errors.append(f"Non-monotonic increase at cycle {self.cycles[i]}: {self.amplitudes[i]} < {self.amplitudes[i-1]}")
                    break
                elif direction == 'decreasing' and self.amplitudes[i] > self.amplitudes[i-1]:
                    self.passed = False
                    self.errors.append(f"Non-monotonic decrease at cycle {self.cycles[i]}: {self.amplitudes[i]} > {self.amplitudes[i-1]}")
                    break
                elif direction == 'non_decreasing' and self.amplitudes[i] < self.amplitudes[i-1]:
                    self.passed = False
                    self.errors.append(f"Decreasing amplitude at cycle {self.cycles[i]}: {self.amplitudes[i]} < {self.amplitudes[i-1]}")
                    break
                elif direction == 'non_increasing' and self.amplitudes[i] > self.amplitudes[i-1]:
                    self.passed = False
                    self.errors.append(f"Increasing amplitude at cycle {self.cycles[i]}: {self.amplitudes[i]} > {self.amplitudes[i-1]}")
                    break

        return self.passed

def run_single_test(config, verbose=False):
    """Run a single test with the given configuration"""

    def tb_process(dut):
        packed_data = config.pack_coefficients()

        yield dut.i.payload.data.eq(packed_data)
        yield dut.i.stb.eq(1)
        yield
        yield dut.i.stb.eq(0)

        total_cycles = config.cycles
        if verbose:
            interval = max(1, min(10, total_cycles // 50))
            output_points = list(range(0, total_cycles + 1, interval))
            if output_points[-1] != total_cycles:
                output_points.append(total_cycles)
        else:
            interval = max(1, total_cycles // 20)
            output_points = [i * interval for i in range(21)]
            if output_points[-1] != total_cycles:
                output_points[-1] = total_cycles

        result = TestResult(config)
        output_index = 0

        for cycle in range(total_cycles + 1):
            shift_stb = yield dut.shift_stb
            shift_counter = yield dut.shift_counter

            result.add_full_cycle_data(cycle, shift_stb)

            if output_index < len(output_points) and cycle == output_points[output_index]:
                amplitude = yield dut.amplitude

                debug_info = {}
                debug_info['ftw'] = yield dut.ftw
                debug_info['atw'] = yield dut.atw
                debug_info['ptw'] = yield dut.ptw
                if verbose:
                    debug_info['shift_counter'] = shift_counter
                    debug_info['x0'] = yield dut.x[0]
                    debug_info['x1'] = yield dut.x[1]
                    debug_info['x2'] = yield dut.x[2]
                    debug_info['x3'] = yield dut.x[3]
                    debug_info['z0'] = yield dut.z[0]
                    debug_info['z1'] = yield dut.z[1]
                    debug_info['z2'] = yield dut.z[2]

                result.add_sample(cycle, amplitude, shift_stb, debug_info)
                output_index += 1

            if cycle < total_cycles:
                yield

        return result

    dut = LTC2000DDSModuleTest()

    def clock():
        for _ in range(config.cycles + 10):
            yield

    result_container = [None]

    def wrapper_tb(dut):
        result_container[0] = yield from tb_process(dut)

    sim = Simulator(dut, [wrapper_tb(dut), clock()])
    sim.run()

    return result_container[0]

def print_test_report(result, verbose=False):
    """Print a detailed report for a single test"""
    config = result.config

    print(f"\n{'='*80}")
    print(f"Test: {config.name}")
    print(f"{'='*80}")

    if config.description:
        print(f"Description: {config.description}")

    print(f"Cycles: {config.cycles}")
    print(f"Shift: {config.shift} (update every {config.get_update_interval()} cycles)")

    print("\nCoefficients:")
    for key, value in config.coefficients.items():
        if key != 'reserved':
            print(f"  {key:12}: 0x{value:08x} ({value:>10})")

    status_color = "PASS" if result.passed else "FAIL"
    print(f"\nResults: {status_color}")

    if result.errors:
        print("\nErrors:")
        for error in result.errors:
            print(f"  - {error}")

    if verbose and result.debug_info and any(result.debug_info):
        print(f"\n{'='*80}")
        print("VERBOSE DEBUG INFORMATION")
        print(f"{'='*80}")

        print("\nCoefficient Evolution (x[] and z[] arrays):")
        print(f"{'Cycle':>6} {'Upd':>4} {'Cnt':>4} {'x[0]':>14} {'x[1]':>14} {'x[2]':>14} {'x[3]':>14} {'z[0]':>12} {'z[1]':>12} {'z[2]':>12}")
        print(f"{'-'*6} {'-'*4} {'-'*4} {'-'*14} {'-'*14} {'-'*14} {'-'*14} {'-'*12} {'-'*12} {'-'*12}")

        for i, (cycle, updated, debug) in enumerate(zip(result.cycles, result.updates, result.debug_info)):
            if debug:
                upd_str = "Yes" if updated else "No"
                counter = debug.get('shift_counter', 0)
                x0 = debug.get('x0', 0)
                x1 = debug.get('x1', 0)
                x2 = debug.get('x2', 0)
                x3 = debug.get('x3', 0)
                z0 = debug.get('z0', 0)
                z1 = debug.get('z1', 0)
                z2 = debug.get('z2', 0)

                print(f"{cycle:6d} {upd_str:>4} {counter:4d} {x0:14,d} {x1:14,d} {x2:14,d} {x3:14,d} {z0:12,d} {z1:12,d} {z2:12,d}")

        print(f"\nDerived Signals:")
        print(f"{'Cycle':>6} {'Amplitude':>12} {'FTW':>12} {'ATW':>14} {'PTW':>10}")
        print(f"{'-'*6} {'-'*12} {'-'*12} {'-'*14} {'-'*10}")

        for i, (cycle, amp, debug) in enumerate(zip(result.cycles, result.amplitudes, result.debug_info)):
            if debug:
                ftw = debug.get('ftw', 0)
                atw = debug.get('atw', 0)
                ptw = debug.get('ptw', 0)
                print(f"{cycle:6d} {amp:12,d} {ftw:12,d} {atw:14,d} {ptw:10,d}")

        print(f"\nUpdate Interval Analysis:")

        if result.full_cycles and result.full_updates:
            update_cycles = [result.full_cycles[i] for i, updated in enumerate(result.full_updates) if updated]
        else:
            update_cycles = [result.cycles[i] for i, updated in enumerate(result.updates) if updated]

        if len(update_cycles) > 1:
            intervals = [update_cycles[i] - update_cycles[i-1] for i in range(1, len(update_cycles))]
            expected_interval = config.get_update_interval()

            print(f"Expected interval: {expected_interval}")
            print(f"Actual intervals: {intervals[:10]}{'...' if len(intervals) > 10 else ''}")
            print(f"All intervals correct: {all(interval == expected_interval for interval in intervals)}")

            wrong_count = 0
            for i, interval in enumerate(intervals):
                if interval != expected_interval:
                    if wrong_count < 5:
                        print(f"  Wrong interval at update {i+1}: {interval} (should be {expected_interval})")
                    wrong_count += 1
            if wrong_count > 5:
                print(f"  ... and {wrong_count - 5} more interval errors")
        else:
            print("Not enough updates to analyze intervals")

    print("\nAmplitude Evolution:")
    if verbose:
        print(f"{'Cycle':>6}   {'Amplitude':>12}   {'Updated':>7}   {'ShiftCnt':>8}   {'Change':>8}")
        print(f"{'-'*6}   {'-'*12}   {'-'*7}   {'-'*8}   {'-'*8}")
    else:
        print(f"{'Cycle':>6}   {'Amplitude':>12}   {'Updated':>7}")
        print(f"{'-'*6}   {'-'*12}   {'-'*7}")

    prev_amp = None
    for i, (cycle, amp, updated) in enumerate(zip(result.cycles, result.amplitudes, result.updates)):
        if verbose and result.debug_info[i]:
            counter = result.debug_info[i].get('shift_counter', 0)
            change = amp - prev_amp if prev_amp is not None else 0
            print(f"{cycle:6d}   0x{amp:04x} ({amp:6,d})   {'Yes' if updated else 'No':>7}   {counter:8d}   {change:+8d}")
        else:
            print(f"{cycle:6d}   0x{amp:04x} ({amp:6,d})   {'Yes' if updated else 'No':>7}")
        prev_amp = amp

def save_csv_report(results, filename):
    """Save test results to CSV file"""
    with open(filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)

        writer.writerow(['Test_Name', 'Cycle', 'Amplitude_Hex', 'Amplitude_Dec', 'Updated',
                        'Shift', 'Update_Interval', 'Passed', 'Errors'])

        for result in results:
            config = result.config
            for i, (cycle, amp, updated) in enumerate(zip(result.cycles, result.amplitudes, result.updates)):
                writer.writerow([
                    config.name,
                    cycle,
                    f"0x{amp:04x}",
                    amp,
                    updated,
                    config.shift,
                    config.get_update_interval(),
                    result.passed,
                    '; '.join(result.errors) if result.errors else ''
                ])

def create_sample_config():
    """Create a sample configuration file"""
    sample_configs = [
        {
            "name": "Basic Linear Ramp",
            "description": "Simple linear amplitude increase",
            "cycles": 50,
            "shift": 0,
            "coefficients": {
                "amp": 1000,
                "damp": 100,
                "ddamp": 0,
                "dddamp": 0
            },
            "validation": {
                "final_amplitude": 6000,
                "amplitude_tolerance": 100,
                "monotonic": "increasing",
                "check_updates": true
            }
        },
        {
            "name": "Quadratic Growth",
            "description": "Quadratic amplitude increase with shift=2",
            "cycles": 100,
            "shift": 2,
            "coefficients": {
                "amp": 500,
                "damp": 10,
                "ddamp": 5,
                "dddamp": 0
            },
            "validation": {
                "monotonic": "increasing",
                "check_updates": true
            }
        },
        {
            "name": "Cubic Polynomial",
            "description": "Full cubic polynomial test",
            "cycles": 80,
            "shift": 1,
            "coefficients": {
                "amp": 2000,
                "damp": -50,
                "ddamp": 2,
                "dddamp": 1
            },
            "validation": {
                "check_updates": true
            }
        },
        {
            "name": "High Shift Test",
            "description": "Test with shift=4 (update every 16 cycles)",
            "cycles": 200,
            "shift": 4,
            "coefficients": {
                "amp": 10000,
                "damp": 200,
                "ddamp": 0,
                "dddamp": 0
            },
            "validation": {
                "monotonic": "increasing",
                "check_updates": true
            }
        },
        {
            "name": "Phase and Frequency Test",
            "description": "Test with phase and frequency components",
            "cycles": 60,
            "shift": 0,
            "coefficients": {
                "amp": 8000,
                "damp": 0,
                "phase_offset": 1000,
                "ftw": 500,
                "chirp": 10
            },
            "validation": {
                "check_updates": true
            }
        }
    ]

    with open('ltc2000_test_config.json', 'w') as f:
        json.dump(sample_configs, f, indent=2)

    print("Created sample configuration file: ltc2000_test_config.json")

def load_test_configs(filename):
    """Load test configurations from JSON file"""
    try:
        with open(filename, 'r') as f:
            config_data = json.load(f)

        configs = []
        for config_dict in config_data:
            configs.append(TestConfiguration(config_dict))

        return configs

    except FileNotFoundError:
        print(f"Configuration file {filename} not found.")
        return []
    except json.JSONDecodeError as e:
        print(f"Error parsing configuration file: {e}")
        return []

def run_test_suite(config_filename="ltc2000_test_config.json"):
    """Run a complete test suite"""

    if not os.path.exists(config_filename):
        print(f"Configuration file {config_filename} not found. Creating sample...")
        create_sample_config()
        return

    configs = load_test_configs(config_filename)
    if not configs:
        print("No valid test configurations found.")
        return

    print(f"Running {len(configs)} tests...")

    results = []
    failed_configs = []

    for i, config in enumerate(configs):
        print(f"\nRunning test {i+1}/{len(configs)}: {config.name}")
        result = run_single_test(config, verbose=False)
        result.validate()
        results.append(result)

        if not result.passed:
            failed_configs.append(config)

    print(f"\n{'='*60}")
    print("TEST SUITE SUMMARY")
    print(f"{'='*60}")

    passed = sum(1 for r in results if r.passed)
    total = len(results)

    print(f"Tests passed: {passed}/{total}")
    print(f"Success rate: {passed/total*100:.1f}%")

    print(f"\n{'Test Name':<40} {'Shift':<6} {'Cycles':<8} {'Result':<8}")
    print(f"{'-'*40} {'-'*6} {'-'*8} {'-'*8}")

    for result in results:
        config = result.config
        status = "PASS" if result.passed else "FAIL"
        print(f"{config.name:<40} {config.shift:<6} {config.cycles:<8} {status:<8}")

    if failed_configs:
        print(f"\n{'='*60}")
        print(f"VERBOSE ANALYSIS OF FAILED TESTS ({len(failed_configs)} tests)")
        print(f"{'='*60}")
        print("Re-running failed tests with detailed debugging information...")

        verbose_results = []
        for i, config in enumerate(failed_configs):
            print(f"\nRe-running failed test {i+1}/{len(failed_configs)}: {config.name}")
            verbose_result = run_single_test(config, verbose=True)
            verbose_result.validate()
            verbose_results.append(verbose_result)
            print_test_report(verbose_result, verbose=True)

    csv_filename = config_filename.replace('.json', '_results.csv')
    save_csv_report(results, csv_filename)
    print(f"\nResults saved to: {csv_filename}")

    return results

if __name__ == "__main__":
    print("LTC2000 DDS Tests")
    print("=================")

    run_test_suite()
