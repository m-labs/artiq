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

    # Make sure everything's valid
    modules = [Module.from_filename(filename, engine=engine)
               for filename in sys.argv[1:]]

    def benchmark(f, name):
        start = time.perf_counter()
        end   = 0
        runs  = 0
        while end - start < 5 or runs < 10:
            f()
            runs += 1
            end = time.perf_counter()

        print("{} {} runs: {:.2f}s, {:.2f}ms/run".format(
                runs, name, end - start, (end - start) / runs * 1000))

    sources = []
    for filename in sys.argv[1:]:
        with open(filename) as f:
            sources.append(f.read())

    benchmark(lambda: [Module.from_string(src) for src in sources],
              "ARTIQ typechecking and transforms")

    benchmark(lambda: OR1KTarget().compile_and_link(modules),
              "LLVM optimization and linking")

if __name__ == "__main__":
    main()
