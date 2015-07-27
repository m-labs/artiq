# RUN: %python -m artiq.compiler.testbench.inferencer +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: ${LINE:+1}: error: return statement outside of a function
return

# CHECK-L: ${LINE:+1}: error: break statement outside of a loop
break

# CHECK-L: ${LINE:+1}: error: continue statement outside of a loop
continue

while True:
    def f():
        # CHECK-L: ${LINE:+1}: error: break statement outside of a loop
        break

        # CHECK-L: ${LINE:+1}: error: continue statement outside of a loop
        continue
