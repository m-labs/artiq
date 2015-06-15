# RUN: %python -m artiq.py2llvm.typing +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

def a():
    # CHECK-L: ${LINE:+1}: error: cannot declare name 'x' as nonlocal: it is not bound in any outer scope
    nonlocal x

x = 1
def b():
    nonlocal x
    # CHECK-L: ${LINE:+1}: error: name 'x' cannot be nonlocal and global simultaneously
    global x

def c():
    global x
    # CHECK-L: ${LINE:+1}: error: name 'x' cannot be global and nonlocal simultaneously
    nonlocal x

def d(x):
    # CHECK-L: ${LINE:+1}: error: name 'x' cannot be a parameter and global simultaneously
    global x

def e(x):
    # CHECK-L: ${LINE:+1}: error: name 'x' cannot be a parameter and nonlocal simultaneously
    nonlocal x

# CHECK-L: ${LINE:+1}: error: duplicate parameter 'x'
def f(x, x):
    pass
