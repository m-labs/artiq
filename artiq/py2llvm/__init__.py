from llvm import core as lc
from llvm import passes as lp

from artiq.py2llvm import values
from artiq.py2llvm.functions import compile_function
from artiq.py2llvm.tools import add_common_passes


def get_runtime_binary(env, funcdef):
    module = lc.Module.new("main")
    env.init_module(module)
    values.init_module(module)

    compile_function(module, env, funcdef, dict())

    pass_manager = lp.PassManager.new()
    add_common_passes(pass_manager)
    pass_manager.run(module)

    return env.emit_object()
