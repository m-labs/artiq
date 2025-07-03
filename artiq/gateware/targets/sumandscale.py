from migen import *
from migen.fhdl import verilog

class SumAndScale(Module):
    def __init__(self):
        self.inputs = [Signal((16, True)) for _ in range(4)]
        self.amplitudes = [Signal((16, True)) for _ in range(4)]
        self.output = Signal((16, True))

        ###

        products = [Signal((32, True)) for _ in range(4)]
        for i in range(4):
            # First, multiply (preserving full 32-bit result)
            self.sync += products[i].eq(self.inputs[i] * self.amplitudes[i])

        # Sum the full 32-bit results
        sum_all = Signal((34, True))  # Extra bits to avoid potential overflow
        self.comb += sum_all.eq(products[0] + products[1] + products[2] + products[3])

        # Finally, shift and saturate
        self.sync += [
            If(sum_all >> 15 > 32767,
                self.output.eq(32767)
            ).Elif(sum_all >> 15 < -32768,
                self.output.eq(-32768)
            ).Else(
                self.output.eq(sum_all >> 15)
            )
        ]

def test_bench():
    dut = SumAndScale()

    sample_data = [
        0x0000, 0x2120, 0x3fff, 0x5a81, 0x6ed9, 0x7ba2, 0x7fff, 0x7ba2, 0x6ed9, 0x5a81,
        0x3fff, 0x2120, 0x0000, 0xdee0, 0xc001, 0xa57f, 0x9127, 0x845e, 0x8001, 0x845e,
        0x9127, 0xa57f, 0xc001, 0xdee0
    ]
    def tb_generator():
        test_amplitudes = [0x2000, 0x4000, 0x8000, 0xFFFF]  # Test with 1/8, 1/4, 1/2 and ~1.0 gain

        DISPLAY_LATENCY = 2

        for amp in test_amplitudes:
            print(f"\nTesting with amplitude {amp:04x}")
            for i in range(3):
                yield dut.amplitudes[i].eq(0)
            yield dut.amplitudes[3].eq(amp)

            outputs = []
            input_indices = []
            NSAMPLES = len(sample_data)
            NCYCLES = NSAMPLES + DISPLAY_LATENCY
            for i in range(NCYCLES):
                if i < NSAMPLES:
                    for j in range(4):
                        yield dut.inputs[j].eq(sample_data[i])
                yield
                if i>=DISPLAY_LATENCY:
                    outputs.append((yield dut.output))

            # Display with outputs shifted up to align with their inputs
            print("     Inputs                          Output")
            print("----------------------------------------")
            for i in range(NSAMPLES):
                if i < NSAMPLES-DISPLAY_LATENCY:  # Regular output
                    print(f"{sample_data[i]:4x} {sample_data[i]:4x} {sample_data[i]:4x} {sample_data[i]:4x} {outputs[i] & 0xFFFF:04x}")

    from migen.sim import run_simulation
    run_simulation(dut, tb_generator(), vcd_name="sum_and_scale.vcd")

if __name__ == "__main__":
    print("Converting to Verilog...")
    dut = SumAndScale()
    print(verilog.convert(dut, ios={*dut.inputs, *dut.amplitudes, dut.output}))
    print("\nRunning testbench...")
    test_bench()
