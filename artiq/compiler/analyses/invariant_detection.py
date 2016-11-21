"""
:class:`InvariantDetection` determines which attributes can be safely
marked kernel invariant.
"""

from pythonparser import diagnostic
from .. import ir, types

class InvariantDetection:
    def __init__(self, engine):
        self.engine = engine

    def process(self, functions):
        self.attr_locs = dict()
        self.attr_written = set()

        for func in functions:
            self.process_function(func)

        for key in self.attr_locs:
            if key not in self.attr_written:
                typ, attr = key
                if attr in typ.constant_attributes:
                    continue

                diag = diagnostic.Diagnostic("note",
                    "attribute '{attr}' of type '{type}' is never written to; " +
                    "it could be marked as kernel invariant to potentially increase performance",
                    {"attr": attr,
                     "type": typ.name},
                    self.attr_locs[key])
                self.engine.process(diag)

    def process_function(self, func):
        for block in func.basic_blocks:
            for insn in block.instructions:
                if not isinstance(insn, (ir.GetAttr, ir.SetAttr)):
                    continue
                if not types.is_instance(insn.object().type):
                    continue

                key = (insn.object().type, insn.attr)
                if isinstance(insn, ir.GetAttr):
                    if types.is_method(insn.type):
                        continue
                    if key not in self.attr_locs and insn.loc is not None:
                        self.attr_locs[key] = insn.loc
                elif isinstance(insn, ir.SetAttr):
                    self.attr_written.add(key)
