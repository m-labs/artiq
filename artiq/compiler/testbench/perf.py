import sys, os, time
from pythonparser import diagnostic
from .. import Module
from ..targets import OR1KTarget

def main():
    if not len(sys.argv) > 1:
        print("Expected at least one module filename", file=sys.stderr)
        exit(1)

    def process_diagnostic(diag):
        print("\n".join(diag.render()), file=sys.stderr)
        if diag.level in ("fatal", "error"):
            exit(1)

    engine = diagnostic.Engine()
    engine.process = process_diagnostic

    modules = []
    for filename in sys.argv[1:]:
        modules.append(Module.from_filename(filename, engine=engine))

    runs = 100
    start = time.perf_counter()
    for _ in range(runs):
        llobj = OR1KTarget().compile_and_link(modules)
    end = time.perf_counter()

    print("{} compilation runs: {:.2f}s, {:.2f}ms/run".format(
            runs, end - start, (end - start) / runs * 1000))

if __name__ == "__main__":
    main()
