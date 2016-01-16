import sys, fileinput
from pythonparser import diagnostic
from ..module import Module, Source

def main():
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
