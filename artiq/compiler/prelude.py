"""
The :mod:`prelude` module contains the initial global environment
in which ARTIQ kernels are evaluated.
"""

from . import builtins

def globals():
    return {
        # Value constructors
        "bool":                 builtins.fn_bool(),
        "int":                  builtins.fn_int(),
        "float":                builtins.fn_float(),
        "str":                  builtins.fn_str(),
        "bytes":                builtins.fn_bytes(),
        "bytearray":            builtins.fn_bytearray(),
        "list":                 builtins.fn_list(),
        "array":                builtins.fn_array(),
        "range":                builtins.fn_range(),
        "int32":                builtins.fn_int32(),
        "int64":                builtins.fn_int64(),

        # Exception constructors
        "Exception":            builtins.fn_Exception(),
        "IndexError":           builtins.fn_IndexError(),
        "ValueError":           builtins.fn_ValueError(),
        "ZeroDivisionError":    builtins.fn_ZeroDivisionError(),

        # Built-in Python functions
        "len":                  builtins.fn_len(),
        "round":                builtins.fn_round(),
        "abs":                  builtins.fn_abs(),
        "min":                  builtins.fn_min(),
        "max":                  builtins.fn_max(),
        "print":                builtins.fn_print(),

        # ARTIQ decorators
        "kernel":               builtins.fn_kernel(),
        "portable":             builtins.fn_kernel(),
        "rpc":                  builtins.fn_kernel(),

        # ARTIQ context managers
        "parallel":             builtins.obj_parallel(),
        "interleave":           builtins.obj_interleave(),
        "sequential":           builtins.obj_sequential(),
        "watchdog":             builtins.fn_watchdog(),

        # ARTIQ time management functions
        "delay":                builtins.fn_delay(),
        "now_mu":               builtins.fn_now_mu(),
        "delay_mu":             builtins.fn_delay_mu(),
        "at_mu":                builtins.fn_at_mu(),

        # ARTIQ utility functions
        "rtio_log":             builtins.fn_rtio_log(),
        "core_log":             builtins.fn_print(),
    }
