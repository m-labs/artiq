from artiq.py2llvm.module import Module

def get_runtime_binary(env, funcdef):
    module = Module(env)
    module.compile_function(funcdef, dict())
    return module.emit_object()
