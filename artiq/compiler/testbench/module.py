import sys, fileinput
from pythonparser import diagnostic
from .. import Module

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "+diag":
        del sys.argv[1]
        def process_diagnostic(diag):
            print("\n".join(diag.render(only_line=True)))
            if diag.level == "fatal":
                exit()
    else:
        def process_diagnostic(diag):
            print("\n".join(diag.render()))
            if diag.level in ("fatal", "error"):
                exit(1)

    engine = diagnostic.Engine()
    engine.process = process_diagnostic

    mod = Module.from_string("".join(fileinput.input()).expandtabs(), engine=engine)
    print(repr(mod))

if __name__ == "__main__":
    main()
