"""
:class:`Interleaver` reorders requests to the RTIO core so that
the timestamp would always monotonically nondecrease.
"""

from .. import ir, iodelay
from ..analyses import domination

class Interleaver:
    def __init__(self, engine):
        self.engine = engine

    def process(self, functions):
        for func in functions:
            self.process_function(func)

    def process_function(self, func):
        for insn in func.instructions():
            if isinstance(insn, ir.Delay):
                if any(insn.expr.free_vars()):
                    # If a function has free variables in delay expressions,
                    # that means its IO delay depends on arguments.
                    # Do not change such functions in any way so that it will
                    # be successfully inlined and then removed by DCE.
                    return

        postdom_tree = None
        for insn in func.instructions():
            if isinstance(insn, ir.Parallel):
                # Lazily compute dominators.
                if postdom_tree is None:
                    postdom_tree = domination.PostDominatorTree(func)

                interleave_until = postdom_tree.immediate_dominator(insn.basic_block)
                assert (interleave_until is not None) # no nonlocal flow in `with parallel`

                target_block  = insn.basic_block
                target_time   = 0
                source_blocks = insn.basic_block.successors()
                source_times  = [0 for _ in source_blocks]

                while len(source_blocks) > 0:
                    def iodelay_of_block(block):
                        terminator = block.terminator()
                        if isinstance(terminator, ir.Delay):
                            # We should be able to fold everything without free variables.
                            assert iodelay.is_const(terminator.expr)
                            return terminator.expr.value
                        else:
                            return 0

                    def time_after_block(pair):
                        index, block = pair
                        return source_times[index] + iodelay_of_block(block)

                    index, source_block = min(enumerate(source_blocks), key=time_after_block)
                    source_block_delay  = iodelay_of_block(source_block)

                    target_terminator = target_block.terminator()
                    if isinstance(target_terminator, (ir.Delay, ir.Branch)):
                        target_terminator.set_target(source_block)
                    elif isinstance(target_terminator, ir.Parallel):
                        target_terminator.replace_with(ir.Branch(source_block))
                    else:
                        assert False

                    new_source_block = postdom_tree.immediate_dominator(source_block)
                    assert (new_source_block is not None)

                    target_block          = source_block
                    target_time          += source_block_delay

                    if new_source_block == interleave_until:
                        # We're finished with this branch.
                        del source_blocks[index]
                        del source_times[index]
                    else:
                        source_blocks[index] = new_source_block
                        source_times[index]  = target_time
