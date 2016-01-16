# RUN: %python -m artiq.compiler.testbench.jit %s
# RUN: %python %s

def fib(x):
    if x == 1:
        return x
    else:
        return x * fib(x - 1)
assert fib(5) == 120

# argument combinations handled in lambda.py
