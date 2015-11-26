import sys, os
from pythonparser import diagnostic
from ..module import Module, Source
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
        modules.append(Module(Source.from_filename(filename, engine=engine)))

    llobj = OR1KTarget().compile_and_link(modules)

    basename, ext = os.path.splitext(sys.argv[-1])
    with open(basename + ".so", "wb") as f:
        f.write(llobj)

if __name__ == "__main__":
    main()
