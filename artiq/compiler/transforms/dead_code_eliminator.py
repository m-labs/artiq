"""
:class:`DeadCodeEliminator` is a dead code elimination transform:
it only basic blocks with no predecessors as well as unused
instructions without side effects.
"""

from .. import ir

class DeadCodeEliminator:
    def __init__(self, engine):
        self.engine = engine

    def process(self, functions):
        for func in functions:
            self.process_function(func)

    def process_function(self, func):
        # defer removing those blocks, so our use checks will ignore deleted blocks
        preserve = [func.entry()]
        work_list = [func.entry()]
        while any(work_list):
            block = work_list.pop()
            for succ in block.successors():
                if succ not in preserve:
                    preserve.append(succ)
                    work_list.append(succ)

        to_be_removed = []
        for block in func.basic_blocks:
            if block not in preserve:
                block.is_removed = True
                to_be_removed.append(block)
                for insn in block.instructions:
                    insn.is_removed = True

        for block in to_be_removed:
            self.remove_block(block)

        modified = True
        while modified:
            modified = False
            for insn in func.instructions():
                # Note that GetLocal is treated as an impure operation:
                # the local access validator has to observe it to emit
                # a diagnostic for reads of uninitialized locals, and
                # it also has to run after the interleaver, but interleaver
                # doesn't like to work with IR before DCE.
                if isinstance(insn, (ir.Phi, ir.Alloc, ir.GetAttr, ir.GetElem, ir.Coerce,
                                     ir.Arith, ir.Compare, ir.Select, ir.Quote, ir.Closure,
                                     ir.Offset)) \
                        and not any(insn.uses):
                    insn.erase()
                    modified = True

    def remove_block(self, block):
        # block.uses are updated while iterating
        for use in set(block.uses):
            if use.is_removed:
                continue
            if isinstance(use, ir.Phi):
                use.remove_incoming_block(block)
                if not any(use.operands):
                    self.remove_instruction(use)
            elif isinstance(use, ir.SetLocal):
                # setlocal %env, %block is only used for lowering finally
                use.erase()
            else:
                assert False

        block.erase()

    def remove_instruction(self, insn):
        for use in set(insn.uses):
            if use.is_removed:
                continue
            if isinstance(use, ir.Phi):
                use.remove_incoming_value(insn)
                if not any(use.operands):
                    self.remove_instruction(use)
            else:
                assert False

        insn.erase()
