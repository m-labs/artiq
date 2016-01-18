# RUN: %python -m artiq.compiler.testbench.inferencer +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

x = 1
def a():
    # CHECK-L: ${LINE:+1}: error: cannot declare name 'x' as nonlocal: it is not bound in any outer scope
    nonlocal x

def f():
    y = 1
    def b():
        nonlocal y
        # CHECK-L: ${LINE:+1}: error: name 'y' cannot be nonlocal and global simultaneously
        global y

    def c():
        global y
        # CHECK-L: ${LINE:+1}: error: name 'y' cannot be global and nonlocal simultaneously
        nonlocal y

    def d(y):
        # CHECK-L: ${LINE:+1}: error: name 'y' cannot be a parameter and global simultaneously
        global y

    def e(y):
        # CHECK-L: ${LINE:+1}: error: name 'y' cannot be a parameter and nonlocal simultaneously
        nonlocal y

# CHECK-L: ${LINE:+1}: error: duplicate parameter 'x'
def f(x, x):
    pass

# CHECK-L: ${LINE:+1}: error: variadic arguments are not supported
def g(*x):
    pass
