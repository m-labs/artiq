import sys, fileinput
from pythonparser import diagnostic
from .. import Module

def main():
    def process_diagnostic(diag):
        print("\n".join(diag.render()))
        if diag.level in ("fatal", "error"):
            exit(1)

    engine = diagnostic.Engine()
    engine.process = process_diagnostic

    mod = Module.from_string("".join(fileinput.input()).expandtabs(), engine=engine)
    for fn in mod.ir:
        print(fn)

if __name__ == "__main__":
    main()
