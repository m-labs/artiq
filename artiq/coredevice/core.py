import os

from artiq.transforms.inline import inline
from artiq.transforms.lower_units import lower_units
from artiq.transforms.fold_constants import fold_constants
from artiq.transforms.unroll_loops import unroll_loops
from artiq.transforms.interleave import interleave
from artiq.transforms.lower_time import lower_time
from artiq.transforms.unparse import Unparser
from artiq.py2llvm import get_runtime_binary


def _unparse(label, node):
    print("*** Unparsing: "+label)
    Unparser(node)


def _make_debug_unparse(final):
    try:
        env = os.environ["ARTIQ_UNPARSE"]
    except KeyError:
        env = ""
    selected_labels = set(env.split())
    if "all" in selected_labels:
        return _unparse
    else:
        if "final" in selected_labels:
            selected_labels.add(final)

        def _filtered_unparse(label, node):
            if label in selected_labels:
                _unparse(label, node)
        return _filtered_unparse


class Core:
    def __init__(self, core_com, runtime_env=None):
        if runtime_env is None:
            runtime_env = core_com.get_runtime_env()
        self.runtime_env = runtime_env
        self.core_com = core_com

    def run(self, k_function, k_args, k_kwargs):
        # transform/simplify AST
        _debug_unparse = _make_debug_unparse("fold_constants_2")

        func_def, rpc_map, exception_map = inline(
            self, k_function, k_args, k_kwargs)
        _debug_unparse("inline", func_def)

        lower_units(func_def, rpc_map)
        _debug_unparse("lower_units", func_def)

        fold_constants(func_def)
        _debug_unparse("fold_constants_1", func_def)

        unroll_loops(func_def, 500)
        _debug_unparse("unroll_loops", func_def)

        interleave(func_def)
        _debug_unparse("interleave", func_def)

        lower_time(func_def,
                   getattr(self.runtime_env, "initial_time", 0),
                   self.runtime_env.ref_period)
        _debug_unparse("lower_time", func_def)

        fold_constants(func_def)
        _debug_unparse("fold_constants_2", func_def)

        # compile to machine code and run
        binary = get_runtime_binary(self.runtime_env, func_def)
        self.core_com.load(binary)
        self.core_com.run(func_def.name)
        self.core_com.serve(rpc_map, exception_map)
