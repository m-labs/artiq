from artiq.py2llvm.module import Module

def get_runtime_binary(env, func_def):
    module = Module(env)
    module.compile_function(func_def, dict())
    return module.emit_object()
