import sys, fileinput
from pythonparser import diagnostic
from ..module import Module, Source
from .. import types, iodelay

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "+diag":
        del sys.argv[1]
        diag = True
        def process_diagnostic(diag):
            print("\n".join(diag.render(only_line=True)))
            if diag.level == "fatal":
                exit()
    else:
        diag = False
        def process_diagnostic(diag):
            print("\n".join(diag.render(colored=False)))
            if diag.level in ("fatal", "error"):
                exit(1)

    if len(sys.argv) > 1 and sys.argv[1] == "+delay":
        del sys.argv[1]
        force_delays = True
    else:
        force_delays = False

    engine = diagnostic.Engine()
    engine.process = process_diagnostic

    try:
        mod = Module(Source.from_string("".join(fileinput.input()).expandtabs(), engine=engine))

        if force_delays:
            for var in mod.globals:
                typ = mod.globals[var].find()
                if types.is_function(typ) and types.is_indeterminate_delay(typ.delay):
                    process_diagnostic(typ.delay.find().cause)

        print(repr(mod))
    except:
        if not diag: raise

if __name__ == "__main__":
    main()
