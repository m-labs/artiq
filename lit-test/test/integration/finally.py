# RUN: %python -m artiq.compiler.testbench.jit %s >%t.1
# RUN: OutputCheck %s --file-to-check=%t.1
# RUN: %python %s >%t.2
# RUN: OutputCheck %s --file-to-check=%t.2
# REQUIRES: exceptions

def f():
    while True:
        try:
            print("f-try")
            break
        finally:
            print("f-finally")
    print("f-out")

def g():
    x = True
    while x:
        try:
            print("g-try")
            x = False
            continue
        finally:
            print("g-finally")
    print("g-out")

def h():
    try:
        print("h-try")
        return 10
    finally:
        print("h-finally")
    print("h-out")
    return 20

def i():
    try:
        print("i-try")
        return 10
    finally:
        print("i-finally")
        return 30
    print("i-out")
    return 20

def j():
    try:
        print("j-try")
    finally:
        print("j-finally")
    print("j-out")

# CHECK-L: f-try
# CHECK-L: f-finally
# CHECK-L: f-out
f()

# CHECK-L: g-try
# CHECK-L: g-finally
# CHECK-L: g-out
g()

# CHECK-L: h-try
# CHECK-L: h-finally
# CHECK-NOT-L: h-out
# CHECK-L: h 10
print("h", h())

# CHECK-L: i-try
# CHECK-L: i-finally
# CHECK-NOT-L: i-out
# CHECK-L: i 30
print("i", i())

# CHECK-L: j-try
# CHECK-L: j-finally
# CHECK-L: j-out
print("j", j())
