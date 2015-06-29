# RUN: %python -m artiq.compiler.typing %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: Exception:<constructor Exception>
Exception

try:
    pass
except Exception:
    pass
except Exception as e:
    # CHECK-L: e:Exception
    e
