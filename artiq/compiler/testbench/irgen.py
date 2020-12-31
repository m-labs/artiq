import sys, os, fileinput
from pythonparser import diagnostic
from .. import ir
from ..module import Module, Source

def main():
    if os.getenv("ARTIQ_IR_NO_LOC") is not None:
        ir.BasicBlock._dump_loc = False

    def process_diagnostic(diag):
        print("\n".join(diag.render()))
        if diag.level in ("fatal", "error"):
            exit(1)

    engine = diagnostic.Engine()
    engine.process = process_diagnostic

    mod = Module(Source.from_string("".join(fileinput.input()).expandtabs(), engine=engine))
    for fn in mod.artiq_ir:
        print(fn)

if __name__ == "__main__":
    main()
