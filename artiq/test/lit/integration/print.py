# RUN: %python -m artiq.compiler.testbench.jit %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: None
print(None)

# CHECK-L: True False
print(True, False)

# CHECK-L: 1 -1
print(1, -1)

# CHECK-L: 10000000000
print(10000000000)

# CHECK-L: 1.5
print(1.5)

# CHECK-L: (True, 1)
print((True, 1))

# CHECK-L: (True,)
print((True,))

# CHECK-L: [1, 2, 3]
print([1, 2, 3])

# CHECK-L: [[1, 2], [3]]
print([[1, 2], [3]])

# CHECK-L: range(0, 10, 1)
print(range(10))

# CHECK-L: array([1, 2])
print(array([1, 2]))

# CHECK-L: bytes([97, 98])
print(b"ab")

# CHECK-L: bytearray([97, 98])
print(bytearray(b"ab"))
