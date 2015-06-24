"""
The :mod:`prelude` module contains the initial global environment
in which ARTIQ kernels are evaluated.
"""

from . import builtins

def globals():
    return {
        "bool":    builtins.TBool(),
        "int":     builtins.TInt(),
        "float":   builtins.TFloat(),
        "round":   builtins.fn_round(),
        "len":     builtins.fn_len(),
        "range":   builtins.fn_range(),
        "syscall": builtins.fn_syscall(),
    }
