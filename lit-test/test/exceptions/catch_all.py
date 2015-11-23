# RUN: %python -m artiq.compiler.testbench.jit %s >%t
# RUN: OutputCheck %s --file-to-check=%t
# REQUIRES: exceptions

def catch(f):
    try:
        f()
    except Exception as e:
        print(e)

# CHECK-L: ZeroDivisionError
catch(lambda: 1/0)
# CHECK-L: IndexError
catch(lambda: [1.0][10])
