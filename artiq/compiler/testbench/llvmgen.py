import sys, fileinput
from pythonparser import diagnostic
from llvmlite import ir as ll
from .. import Module

def main():
    def process_diagnostic(diag):
        print("\n".join(diag.render()))
        if diag.level in ("fatal", "error"):
            exit(1)

    engine = diagnostic.Engine()
    engine.process = process_diagnostic

    llmod = Module.from_string("".join(fileinput.input()).expandtabs(), engine=engine).llvm_ir
    print(llmod)

if __name__ == "__main__":
    main()
