import os

from artiq.language.core import *
from artiq.language.db import *

from artiq.transforms.inline import inline
from artiq.transforms.lower_units import lower_units
from artiq.transforms.quantize_time import quantize_time
from artiq.transforms.remove_inter_assigns import remove_inter_assigns
from artiq.transforms.fold_constants import fold_constants
from artiq.transforms.remove_dead_code import remove_dead_code
from artiq.transforms.unroll_loops import unroll_loops
from artiq.transforms.interleave import interleave
from artiq.transforms.lower_time import lower_time
from artiq.transforms.unparse import unparse

from artiq.py2llvm import get_runtime_binary


def _announce_unparse(label, node):
    print("*** Unparsing: "+label)
    print(unparse(node))


def _make_debug_unparse(final):
    try:
        env = os.environ["ARTIQ_UNPARSE"]
    except KeyError:
        env = ""
    selected_labels = set(env.split())
    if "all" in selected_labels:
        return _announce_unparse
    else:
        if "final" in selected_labels:
            selected_labels.add(final)

        def _filtered_unparse(label, node):
            if label in selected_labels:
                _announce_unparse(label, node)
        return _filtered_unparse


def _no_debug_unparse(label, node):
    pass


class Core(AutoDB):
    class DBKeys:
        comm = Device()
        external_clock = Parameter(None)

    def build(self):
        self.runtime_env = self.comm.get_runtime_env()
        self.core = self

        if self.external_clock is None:
            self.ref_period = self.runtime_env.internal_ref_period
            self.comm.switch_clock(False)
        else:
            self.ref_period = 1/self.external_clock
            self.comm.switch_clock(True)
        self.initial_time = int64(self.runtime_env.warmup_time/self.ref_period)

    def transform_stack(self, func_def, rpc_map, exception_map,
                        debug_unparse=_no_debug_unparse):
        lower_units(func_def, rpc_map)
        debug_unparse("lower_units", func_def)

        remove_inter_assigns(func_def)
        debug_unparse("remove_inter_assigns_1", func_def)

        quantize_time(func_def, self.ref_period.amount)
        debug_unparse("quantize_time", func_def)

        fold_constants(func_def)
        debug_unparse("fold_constants_1", func_def)

        unroll_loops(func_def, 500)
        debug_unparse("unroll_loops", func_def)

        interleave(func_def)
        debug_unparse("interleave", func_def)

        lower_time(func_def, self.initial_time)
        debug_unparse("lower_time", func_def)

        remove_inter_assigns(func_def)
        debug_unparse("remove_inter_assigns_2", func_def)

        fold_constants(func_def)
        debug_unparse("fold_constants_2", func_def)

        remove_dead_code(func_def)
        debug_unparse("remove_dead_code_1", func_def)

        remove_inter_assigns(func_def)
        debug_unparse("remove_inter_assigns_3", func_def)

        fold_constants(func_def)
        debug_unparse("fold_constants_3", func_def)

        remove_dead_code(func_def)
        debug_unparse("remove_dead_code_2", func_def)

    def run(self, k_function, k_args, k_kwargs):
        # transform/simplify AST
        debug_unparse = _make_debug_unparse("remove_dead_code_2")

        func_def, rpc_map, exception_map = inline(
            self, k_function, k_args, k_kwargs)
        debug_unparse("inline", func_def)

        self.transform_stack(func_def, rpc_map, exception_map, debug_unparse)

        # compile to machine code and run
        binary = get_runtime_binary(self.runtime_env, func_def)
        self.comm.load(binary)
        self.comm.run(func_def.name)
        self.comm.serve(rpc_map, exception_map)

    @kernel
    def get_rtio_time(self):
        return cycles_to_time(syscall("rtio_get_counter"))

    @kernel
    def recover_underflow(self):
        t = syscall("rtio_get_counter") + self.initial_time
        at(cycles_to_time(t))
