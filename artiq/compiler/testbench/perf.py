import sys, os
from pythonparser import diagnostic
from ..module import Module, Source
from ..targets import OR1KTarget
from . import benchmark

def main():
    if not len(sys.argv) == 2:
        print("Expected exactly one module filename", file=sys.stderr)
        exit(1)

    def process_diagnostic(diag):
        print("\n".join(diag.render()), file=sys.stderr)
        if diag.level in ("fatal", "error"):
            exit(1)

    engine = diagnostic.Engine()
    engine.process = process_diagnostic

    # Make sure everything's valid
    filename = sys.argv[1]
    with open(filename) as f:
        code = f.read()
    source = Source.from_string(code, filename, engine=engine)
    module = Module(source)

    benchmark(lambda: Source.from_string(code, filename),
              "ARTIQ parsing and inference")

    benchmark(lambda: Module(source),
              "ARTIQ transforms and validators")

    benchmark(lambda: OR1KTarget().compile_and_link([module]),
              "LLVM optimization and linking")

if __name__ == "__main__":
    main()
