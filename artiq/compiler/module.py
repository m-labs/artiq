"""
The :class:`Module` class encapsulates a single Python
"""

import os
from pythonparser import source, diagnostic, parse_buffer
from . import prelude, types, transforms

class Module:
    def __init__(self, source_buffer, engine=diagnostic.Engine(all_errors_are_fatal=True)):
        parsetree, comments = parse_buffer(source_buffer, engine=engine)
        self.name = os.path.basename(source_buffer.name)

        asttyped_rewriter = transforms.ASTTypedRewriter(engine=engine)
        typedtree = asttyped_rewriter.visit(parsetree)
        self.globals = asttyped_rewriter.globals

        inferencer = transforms.Inferencer(engine=engine)
        inferencer.visit(typedtree)

    @classmethod
    def from_string(klass, source_string, name="input.py", first_line=1):
        return klass(source.Buffer(source_string + "\n", name, first_line))

    @classmethod
    def from_filename(klass, filename):
        with open(filename) as f:
            return klass(source.Buffer(f.read(), filename, 1))

    def __repr__(self):
        printer = types.TypePrinter()
        globals = ["%s: %s" % (var, printer.name(self.globals[var])) for var in self.globals]
        return "<artiq.compiler.Module %s {\n  %s\n}>" % (repr(self.name), ",\n  ".join(globals))
