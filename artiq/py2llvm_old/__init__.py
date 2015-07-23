from artiq.py2llvm.module import Module

def get_runtime_binary(runtime, func_def):
    module = Module(runtime)
    module.compile_function(func_def, dict())
    return module.emit_object()
