import sys, fileinput
from ctypes import CFUNCTYPE
from pythonparser import diagnostic
from llvmlite import binding as llvm
from .. import Module

llvm.initialize()
llvm.initialize_native_target()
llvm.initialize_native_asmprinter()
llvm.check_jit_execution()

def main():
    def process_diagnostic(diag):
        print("\n".join(diag.render()))
        if diag.level in ("fatal", "error"):
            exit(1)

    engine = diagnostic.Engine()
    engine.process = process_diagnostic

    source = "".join(fileinput.input())
    source = source.replace("#ARTIQ#", "")
    llmod = Module.from_string(source.expandtabs(), engine=engine).llvm_ir

    lltarget = llvm.Target.from_default_triple()
    llmachine = lltarget.create_target_machine()
    llparsedmod = llvm.parse_assembly(str(llmod))
    llparsedmod.verify()
    lljit = llvm.create_mcjit_compiler(llparsedmod, llmachine)
    lljit.finalize_object()
    llmain = lljit.get_pointer_to_global(llparsedmod.get_function(llmod.name + ".__modinit__"))
    CFUNCTYPE(None)(llmain)()

if __name__ == "__main__":
    main()
