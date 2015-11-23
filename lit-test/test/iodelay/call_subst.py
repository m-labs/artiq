# RUN: %python -m artiq.compiler.testbench.signature %s >%t
# RUN: OutputCheck %s --file-to-check=%t

def pulse(len):
    # "on"
    delay_mu(len)
    # "off"
    delay_mu(len)

# CHECK-L: f: ()->NoneType delay(600 mu)
def f():
    pulse(100)
    pulse(200)
