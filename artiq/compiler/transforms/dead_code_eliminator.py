"""
:class:`DeadCodeEliminator` is a very simple dead code elimination
transform: it only removes basic blocks with no predecessors.
"""

from .. import ir

class DeadCodeEliminator:
    def __init__(self, engine):
        self.engine = engine

    def process(self, functions):
        for func in functions:
            self.process_function(func)

    def process_function(self, func):
        for block in func.basic_blocks:
            if not any(block.predecessors()) and block != func.entry():
                self.remove_block(block)

    def remove_block(self, block):
        # block.uses are updated while iterating
        for use in set(block.uses):
            if isinstance(use, ir.Phi):
                use.remove_incoming_block(block)
                if not any(use.operands):
                    self.remove_instruction(use)
            elif isinstance(use, ir.SetLocal):
                # Setting the target for `finally` resumption, e.g.
                #   setlocal(.k) %v.4, label %try.doreturn
                use.erase()
            else:
                assert False

        block.erase()

    def remove_instruction(self, insn):
        for use in set(insn.uses):
            if isinstance(use, ir.Phi):
                use.remove_incoming_value(insn)
                if not any(use.operands):
                    self.remove_instruction(use)

        insn.erase()
