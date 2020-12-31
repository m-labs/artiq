# RUN: %python -m artiq.compiler.testbench.irgen %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: %BLT.round = numpy.int64 builtin(round) float
def frequency_to_ftw(frequency):
    return int64(round(1e-9*frequency))

frequency_to_ftw(1e9)
