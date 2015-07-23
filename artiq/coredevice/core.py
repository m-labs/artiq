import os

from artiq.language.core import *
from artiq.language.units import ns

from artiq.transforms.inline import inline
from artiq.transforms.quantize_time import quantize_time
from artiq.transforms.remove_inter_assigns import remove_inter_assigns
from artiq.transforms.fold_constants import fold_constants
from artiq.transforms.remove_dead_code import remove_dead_code
from artiq.transforms.unroll_loops import unroll_loops
from artiq.transforms.interleave import interleave
from artiq.transforms.lower_time import lower_time
from artiq.transforms.unparse import unparse

from artiq.coredevice.runtime import Runtime

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


class Core:
    def __init__(self, dmgr, ref_period=8*ns, external_clock=False):
        self.comm = dmgr.get("comm")
        self.ref_period = ref_period
        self.external_clock = external_clock

        self.first_run = True
        self.core = self
        self.comm.core = self
        self.runtime = Runtime()

    def transform_stack(self, func_def, rpc_map, exception_map,
                        debug_unparse=_no_debug_unparse):
        remove_inter_assigns(func_def)
        debug_unparse("remove_inter_assigns_1", func_def)

        quantize_time(func_def, self.ref_period)
        debug_unparse("quantize_time", func_def)

        fold_constants(func_def)
        debug_unparse("fold_constants_1", func_def)

        unroll_loops(func_def, 500)
        debug_unparse("unroll_loops", func_def)

        interleave(func_def)
        debug_unparse("interleave", func_def)

        lower_time(func_def)
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

    def compile(self, k_function, k_args, k_kwargs, with_attr_writeback=True):
        debug_unparse = _make_debug_unparse("remove_dead_code_2")

        func_def, rpc_map, exception_map = inline(
            self, k_function, k_args, k_kwargs, with_attr_writeback)
        debug_unparse("inline", func_def)
        self.transform_stack(func_def, rpc_map, exception_map, debug_unparse)

        binary = get_runtime_binary(self.runtime, func_def)

        return binary, rpc_map, exception_map

    def run(self, k_function, k_args, k_kwargs):
        if self.first_run:
            self.comm.check_ident()
            self.comm.switch_clock(self.external_clock)

        binary, rpc_map, exception_map = self.compile(
            k_function, k_args, k_kwargs)
        self.comm.load(binary)
        self.comm.run(k_function.__name__)
        self.comm.serve(rpc_map, exception_map)
        self.first_run = False

    @kernel
    def get_rtio_counter_mu(self):
        return syscall("rtio_get_counter")

    @kernel
    def break_realtime(self):
        at_mu(syscall("rtio_get_counter") + 125000)
