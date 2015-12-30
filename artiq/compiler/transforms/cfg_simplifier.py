"""
:class:`CFGSimplifier` is a simple control flow graph
simplification transform: it removes empty basic blocks.
"""

from .. import ir

class CFGSimplifier:
    def __init__(self, engine):
        self.engine = engine

    def process(self, functions):
        for func in functions:
            self.process_function(func)

    def process_function(self, func):
        for block in list(func.basic_blocks):
            if len(block.instructions) == 1 and \
                    isinstance(block.terminator(), ir.Branch):
                successor, = block.successors()

                for insn in set(block.uses):
                    if isinstance(insn, ir.BranchIf) and \
                            ((insn.if_true() == block and insn.if_false() == successor) or
                             (insn.if_true() == successor and insn.if_false() == block)):
                        # Our IR doesn't tolerate branch_if %c, %b, %b
                        insn.replace_with(ir.Branch(successor))
                    elif isinstance(insn, ir.Phi):
                        insn.remove_incoming_block(block)

                block.replace_all_uses_with(successor)
                block.erase()
