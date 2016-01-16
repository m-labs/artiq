# RUN: %python -m artiq.compiler.testbench.jit %s
# RUN: %python %s

class contextmgr:
    def __enter__(self):
        print(2)

    def __exit__(self, n1, n2, n3):
        print(4)

# CHECK-L: a 1
# CHECK-L: 2
# CHECK-L: a 3
# CHECK-L: 4
# CHECK-L: a 5
print("a", 1)
with contextmgr():
    print("a", 3)
print("a", 5)

# CHECK-L: b 1
# CHECK-L: 2
# CHECK-L: 4
# CHECK-L: b 6
try:
    print("b", 1)
    with contextmgr():
        [0][1]
        print("b", 3)
    print("b", 5)
except:
    pass
print("b", 6)
