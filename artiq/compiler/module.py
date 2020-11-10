"""
The :class:`Module` class encapsulates a single Python module,
which corresponds to a single ARTIQ translation unit (one LLVM
bitcode file and one object file, unless LTO is used).
A :class:`Module` can be created from a typed AST.

The :class:`Source` class parses a single source file or
string and infers types for it using a trivial :module:`prelude`.
"""

import os
from pythonparser import source, diagnostic, parse_buffer
from . import prelude, types, transforms, analyses, validators

class Source:
    def __init__(self, source_buffer, engine=None):
        if engine is None:
            self.engine = diagnostic.Engine(all_errors_are_fatal=True)
        else:
            self.engine = engine
        self.embedding_map = None
        self.name, _ = os.path.splitext(os.path.basename(source_buffer.name))

        asttyped_rewriter = transforms.ASTTypedRewriter(engine=engine,
                                                        prelude=prelude.globals())
        inferencer = transforms.Inferencer(engine=engine)

        self.parsetree, self.comments = parse_buffer(source_buffer, engine=engine)
        self.typedtree = asttyped_rewriter.visit(self.parsetree)
        self.globals = asttyped_rewriter.globals
        inferencer.visit(self.typedtree)

    @classmethod
    def from_string(cls, source_string, name="input.py", first_line=1, engine=None):
        return cls(source.Buffer(source_string + "\n", name, first_line), engine=engine)

    @classmethod
    def from_filename(cls, filename, engine=None):
        with open(filename) as f:
            return cls(source.Buffer(f.read(), filename, 1), engine=engine)

class Module:
    def __init__(self, src, ref_period=1e-6, attribute_writeback=True, remarks=False):
        self.attribute_writeback = attribute_writeback
        self.engine = src.engine
        self.embedding_map = src.embedding_map
        self.name = src.name
        self.globals = src.globals

        int_monomorphizer = transforms.IntMonomorphizer(engine=self.engine)
        cast_monomorphizer = transforms.CastMonomorphizer(engine=self.engine)
        inferencer = transforms.Inferencer(engine=self.engine)
        monomorphism_validator = validators.MonomorphismValidator(engine=self.engine)
        escape_validator = validators.EscapeValidator(engine=self.engine)
        iodelay_estimator = transforms.IODelayEstimator(engine=self.engine,
                                                        ref_period=ref_period)
        constness_validator = validators.ConstnessValidator(engine=self.engine)
        artiq_ir_generator = transforms.ARTIQIRGenerator(engine=self.engine,
                                                         module_name=src.name,
                                                         ref_period=ref_period)
        dead_code_eliminator = transforms.DeadCodeEliminator(engine=self.engine)
        local_access_validator = validators.LocalAccessValidator(engine=self.engine)
        local_demoter = transforms.LocalDemoter()
        constant_hoister = transforms.ConstantHoister()
        devirtualization = analyses.Devirtualization()
        interleaver = transforms.Interleaver(engine=self.engine)
        invariant_detection = analyses.InvariantDetection(engine=self.engine)

        int_monomorphizer.visit(src.typedtree)
        cast_monomorphizer.visit(src.typedtree)
        inferencer.visit(src.typedtree)
        monomorphism_validator.visit(src.typedtree)
        escape_validator.visit(src.typedtree)
        iodelay_estimator.visit_fixpoint(src.typedtree)
        constness_validator.visit(src.typedtree)
        devirtualization.visit(src.typedtree)
        self.artiq_ir = artiq_ir_generator.visit(src.typedtree)
        artiq_ir_generator.annotate_calls(devirtualization)
        dead_code_eliminator.process(self.artiq_ir)
        interleaver.process(self.artiq_ir)
        local_access_validator.process(self.artiq_ir)
        local_demoter.process(self.artiq_ir)
        constant_hoister.process(self.artiq_ir)
        if remarks:
            invariant_detection.process(self.artiq_ir)

    def build_llvm_ir(self, target):
        """Compile the module to LLVM IR for the specified target."""
        llvm_ir_generator = transforms.LLVMIRGenerator(
            engine=self.engine, module_name=self.name, target=target,
            embedding_map=self.embedding_map)
        return llvm_ir_generator.process(self.artiq_ir,
            attribute_writeback=self.attribute_writeback)

    def __repr__(self):
        printer = types.TypePrinter()
        globals = ["%s: %s" % (var, printer.name(self.globals[var])) for var in self.globals]
        return "<artiq.compiler.Module %s {\n  %s\n}>" % (repr(self.name), ",\n  ".join(globals))
