"""
:class:`Interleaver` reorders requests to the RTIO core so that
the timestamp would always monotonically nondecrease.
"""

from .. import types, builtins, ir, iodelay
from ..analyses import domination

def delay_free_subgraph(root, limit):
    visited = set()
    queue   = root.successors()
    while len(queue) > 0:
        block = queue.pop()
        visited.add(block)

        if block is limit:
            continue

        if isinstance(block.terminator(), ir.Delay):
            return False

        for successor in block.successors():
            if successor not in visited:
                queue.append(successor)

    return True

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
            if not isinstance(insn, ir.Parallel):
                continue

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

                new_target_time   = source_times[index] + source_block_delay
                target_time_delta = new_target_time - target_time

                target_terminator = target_block.terminator()
                if isinstance(target_terminator, ir.Parallel):
                    target_terminator.replace_with(ir.Branch(source_block))
                else:
                    assert isinstance(target_terminator, (ir.Delay, ir.Branch))
                    target_terminator.set_target(source_block)

                source_terminator = source_block.terminator()

                if isinstance(source_terminator, ir.Delay):
                    old_decomp = source_terminator.decomposition()
                else:
                    old_decomp = None

                if target_time_delta > 0:
                    assert isinstance(source_terminator, ir.Delay)

                    if isinstance(old_decomp, ir.Builtin) and \
                            old_decomp.op in ("delay", "delay_mu"):
                        new_decomp_expr = ir.Constant(target_time_delta, builtins.TInt64())
                        new_decomp = ir.Builtin("delay_mu", [new_decomp_expr], builtins.TNone())
                        new_decomp.loc = old_decomp.loc
                        source_terminator.basic_block.insert(source_terminator, new_decomp)
                    else:
                        old_decomp, new_decomp = None, old_decomp

                    source_terminator.replace_with(ir.Delay(iodelay.Const(target_time_delta), {},
                                                            new_decomp, source_terminator.target()))
                else:
                    source_terminator.replace_with(ir.Branch(source_terminator.target()))

                if old_decomp is not None:
                    old_decomp.erase()

                target_block = source_block
                target_time  = new_target_time

                new_source_block = postdom_tree.immediate_dominator(source_block)
                assert (new_source_block is not None)
                assert delay_free_subgraph(source_block, new_source_block)

                if new_source_block == interleave_until:
                    # We're finished with this branch.
                    del source_blocks[index]
                    del source_times[index]
                else:
                    source_blocks[index] = new_source_block
                    source_times[index]  = new_target_time
