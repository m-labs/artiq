from artiq.transforms.inline import inline
from artiq.transforms.lower_units import lower_units
from artiq.transforms.fold_constants import fold_constants
from artiq.transforms.unroll_loops import unroll_loops
from artiq.transforms.interleave import interleave
from artiq.transforms.lower_time import lower_time
from artiq.py2llvm import get_runtime_binary


class Core:
    def __init__(self, core_com, runtime_env=None):
        if runtime_env is None:
            runtime_env = core_com.get_runtime_env()
        self.runtime_env = runtime_env
        self.core_com = core_com

    def run(self, k_function, k_args, k_kwargs):
        funcdef, rpc_map = inline(self, k_function, k_args, k_kwargs)
        lower_units(funcdef, self.runtime_env.ref_period)
        fold_constants(funcdef)
        unroll_loops(funcdef, 50)
        interleave(funcdef)
        lower_time(funcdef, getattr(self.runtime_env, "initial_time", 0))
        fold_constants(funcdef)

        binary = get_runtime_binary(self.runtime_env, funcdef)
        self.core_com.run(binary)
        self.core_com.serve(rpc_map)
