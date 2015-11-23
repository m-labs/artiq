# RUN: %python -m artiq.compiler.testbench.jit %s >%t
# RUN: OutputCheck %s --file-to-check=%t
# REQUIRES: exceptions

def catch(f):
    try:
        f()
    except ZeroDivisionError as zde:
        print(zde)
    except IndexError as ie:
        print(ie)

# CHECK-L: ZeroDivisionError
catch(lambda: 1/0)
# CHECK-L: IndexError
catch(lambda: [1.0][10])
