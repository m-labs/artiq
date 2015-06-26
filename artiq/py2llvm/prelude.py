"""
The :mod:`prelude` module contains the initial global environment
in which ARTIQ kernels are evaluated.
"""

from . import builtins

def globals():
    return {
        "bool":    builtins.fn_bool(),
        "int":     builtins.fn_int(),
        "float":   builtins.fn_float(),
        "list":    builtins.fn_list(),
        "len":     builtins.fn_len(),
        "round":   builtins.fn_round(),
        "range":   builtins.fn_range(),
        "syscall": builtins.fn_syscall(),
    }
