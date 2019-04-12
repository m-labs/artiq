# RUN: %python -m artiq.compiler.testbench.inferencer %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: bool:<constructor bool {}>():bool
bool()

# CHECK-L: bool:<constructor bool>([]:list(elt='a)):bool
bool([])

# CHECK-L: int:<constructor int {}>():numpy.int?
int()

# CHECK-L: int:<constructor int>(1.0:float):numpy.int?
int(1.0)

# CHECK-L: int64:<function int64>(1.0:float):numpy.int64
int64(1.0)

# CHECK-L: float:<constructor float {}>():float
float()

# CHECK-L: float:<constructor float>(1:numpy.int?):float
float(1)

# CHECK-L: list:<constructor list {}>():list(elt='b)
list()

# CHECK-L: len:<function len>([]:list(elt='c)):numpy.int32
len([])

# CHECK-L: round:<function round>(1.0:float):numpy.int?
round(1.0)

# CHECK-L: abs:<function abs>(1:numpy.int?):numpy.int?
abs(1)

# CHECK-L: abs:<function abs>(1.0:float):float
abs(1.0)
