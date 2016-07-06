# RUN: %python -m artiq.compiler.testbench.inferencer %s >%t
# RUN: OutputCheck %s --file-to-check=%t

1 | 2
# CHECK-L: 1:numpy.int?:numpy.int? | 2:numpy.int?:numpy.int?:numpy.int?

1 + 2
# CHECK-L: 1:numpy.int?:numpy.int? + 2:numpy.int?:numpy.int?:numpy.int?

(1,) + (2.0,)
# CHECK-L: (1:numpy.int?,):(numpy.int?,) + (2.0:float,):(float,):(numpy.int?, float)

[1] + [2]
# CHECK-L: [1:numpy.int?]:list(elt=numpy.int?) + [2:numpy.int?]:list(elt=numpy.int?):list(elt=numpy.int?)

1 * 2
# CHECK-L: 1:numpy.int?:numpy.int? * 2:numpy.int?:numpy.int?:numpy.int?

[1] * 2
# CHECK-L: [1:numpy.int?]:list(elt=numpy.int?) * 2:numpy.int?:list(elt=numpy.int?)

1 // 2
# CHECK-L: 1:numpy.int?:numpy.int? // 2:numpy.int?:numpy.int?:numpy.int?

1 + 1.0
# CHECK-L: 1:numpy.int?:float + 1.0:float:float

a = []; a += [1]
# CHECK-L: a:list(elt=numpy.int?) = []:list(elt=numpy.int?); a:list(elt=numpy.int?) += [1:numpy.int?]:list(elt=numpy.int?)

[] is [1]
# CHECK-L: []:list(elt=numpy.int?) is [1:numpy.int?]:list(elt=numpy.int?):bool

1 in [1]
# CHECK-L: 1:numpy.int? in [1:numpy.int?]:list(elt=numpy.int?):bool

[] < [1]
# CHECK-L: []:list(elt=numpy.int?) < [1:numpy.int?]:list(elt=numpy.int?):bool

1.0 < 1
# CHECK-L: 1.0:float < 1:numpy.int?:float:bool
