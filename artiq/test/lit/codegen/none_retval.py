# RUN: %python -m artiq.compiler.testbench.llvmgen %s

def make_none():
    return None

def take_arg(arg):
    pass

def run():
    retval = make_none()
    take_arg(retval)
