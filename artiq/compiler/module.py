"""
The :class:`Module` class encapsulates a single Python
"""

import os
from pythonparser import source, diagnostic, parse_buffer
from . import prelude, types, transforms, validators

class Module:
    def __init__(self, source_buffer, engine=None):
        if engine is None:
            engine = diagnostic.Engine(all_errors_are_fatal=True)

        self.name, _ = os.path.splitext(os.path.basename(source_buffer.name))

        asttyped_rewriter = transforms.ASTTypedRewriter(engine=engine)
        inferencer = transforms.Inferencer(engine=engine)
        int_monomorphizer = transforms.IntMonomorphizer(engine=engine)
        monomorphism_validator = validators.MonomorphismValidator(engine=engine)
        escape_validator = validators.EscapeValidator(engine=engine)
        ir_generator = transforms.IRGenerator(engine=engine, module_name=self.name)
        dead_code_eliminator = transforms.DeadCodeEliminator(engine=engine)
        local_access_validator = validators.LocalAccessValidator(engine=engine)

        self.parsetree, self.comments = parse_buffer(source_buffer, engine=engine)
        self.typedtree = asttyped_rewriter.visit(self.parsetree)
        self.globals = asttyped_rewriter.globals
        inferencer.visit(self.typedtree)
        int_monomorphizer.visit(self.typedtree)
        inferencer.visit(self.typedtree)
        monomorphism_validator.visit(self.typedtree)
        escape_validator.visit(self.typedtree)
        self.ir = ir_generator.visit(self.typedtree)
        dead_code_eliminator.process(self.ir)
        local_access_validator.process(self.ir)

    @classmethod
    def from_string(cls, source_string, name="input.py", first_line=1, engine=None):
        return cls(source.Buffer(source_string + "\n", name, first_line), engine=engine)

    @classmethod
    def from_filename(cls, filename, engine=None):
        with open(filename) as f:
            return cls(source.Buffer(f.read(), filename, 1), engine=engine)

    def __repr__(self):
        printer = types.TypePrinter()
        globals = ["%s: %s" % (var, printer.name(self.globals[var])) for var in self.globals]
        return "<artiq.compiler.Module %s {\n  %s\n}>" % (repr(self.name), ",\n  ".join(globals))
