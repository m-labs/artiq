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
        "list":                 builtins.fn_list(),
        "range":                builtins.fn_range(),

        # Exception constructors
        "Exception":            builtins.fn_Exception(),
        "IndexError":           builtins.fn_IndexError(),
        "ValueError":           builtins.fn_ValueError(),
        "ZeroDivisionError":    builtins.fn_ZeroDivisionError(),

        # Built-in Python functions
        "len":                  builtins.fn_len(),
        "round":                builtins.fn_round(),
        "print":                builtins.fn_print(),

        # ARTIQ decorators
        "kernel":               builtins.fn_kernel(),
        "portable":             builtins.fn_kernel(),

        # ARTIQ context managers
        "parallel":             builtins.obj_parallel(),
        "sequential":           builtins.obj_sequential(),
        "watchdog":             builtins.fn_watchdog(),

        # ARTIQ time management functions
        "now":                  builtins.fn_now(),
        "delay":                builtins.fn_delay(),
        "at":                   builtins.fn_at(),
        "now_mu":               builtins.fn_now_mu(),
        "delay_mu":             builtins.fn_delay_mu(),
        "at_mu":                builtins.fn_at_mu(),
        "mu_to_seconds":        builtins.fn_mu_to_seconds(),
        "seconds_to_mu":        builtins.fn_seconds_to_mu(),

        # ARTIQ utility functions
        "rtio_log":             builtins.fn_rtio_log(),
    }
