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
        func_def, rpc_map = inline(self, k_function, k_args, k_kwargs)
        lower_units(func_def, self.runtime_env.ref_period)
        fold_constants(func_def)
        unroll_loops(func_def, 50)
        interleave(func_def)
        lower_time(func_def, getattr(self.runtime_env, "initial_time", 0))
        fold_constants(func_def)

        binary = get_runtime_binary(self.runtime_env, func_def)
        self.core_com.load(binary)
        self.core_com.run(func_def.name)
        self.core_com.serve(rpc_map)
