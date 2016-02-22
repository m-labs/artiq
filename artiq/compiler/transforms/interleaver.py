"""
:class:`Interleaver` reorders requests to the RTIO core so that
the timestamp would always monotonically nondecrease.
"""

from pythonparser import diagnostic

from .. import types, builtins, ir, iodelay
from ..analyses import domination
from ..algorithms import inline, unroll

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

def iodelay_of_block(block):
    terminator = block.terminator()
    if isinstance(terminator, ir.Delay):
        # We should be able to fold everything without free variables.
        folded_expr = terminator.interval.fold()
        assert iodelay.is_const(folded_expr)
        return folded_expr.value
    else:
        return 0

def is_pure_delay(insn):
    return isinstance(insn, ir.Builtin) and insn.op in ("delay", "delay_mu")

def is_impure_delay_block(block):
    terminator = block.terminator()
    return isinstance(terminator, ir.Delay) and \
            not is_pure_delay(terminator.decomposition())

class Interleaver:
    def __init__(self, engine):
        self.engine = engine

    def process(self, functions):
        for func in functions:
            self.process_function(func)

    def process_function(self, func):
        for insn in func.instructions():
            if isinstance(insn, ir.Delay):
                if any(insn.interval.free_vars()):
                    # If a function has free variables in delay expressions,
                    # that means its IO delay depends on arguments.
                    # Do not change such functions in any way so that it will
                    # be successfully inlined and then removed by DCE.
                    return

        postdom_tree = None
        for insn in func.instructions():
            if not isinstance(insn, ir.Interleave):
                continue

            # Lazily compute dominators.
            if postdom_tree is None:
                postdom_tree = domination.PostDominatorTree(func)

            target_block  = insn.basic_block
            target_time   = 0
            source_blocks = insn.basic_block.successors()
            source_times  = [0 for _ in source_blocks]

            if len(source_blocks) == 1:
                # Immediate dominator for a interleave instruction with one successor
                # is the first instruction in the body of the statement which created
                # it, but below we expect that it would be the first instruction after
                # the statement itself.
                insn.replace_with(ir.Branch(source_blocks[0]))
                continue

            interleave_until = postdom_tree.immediate_dominator(insn.basic_block)
            assert interleave_until is not None # no nonlocal flow in `with interleave`
            assert interleave_until not in source_blocks

            while len(source_blocks) > 0:
                def time_after_block(pair):
                    index, block = pair
                    return source_times[index] + iodelay_of_block(block)

                # Always prefer impure blocks (with calls) to pure blocks, because
                # impure blocks may expand with smaller delays appearing, and in
                # case of a tie, if a pure block is preferred, this would violate
                # the timeline monotonicity.
                available_source_blocks = list(filter(is_impure_delay_block, source_blocks))
                if not any(available_source_blocks):
                    available_source_blocks = source_blocks

                index, source_block = min(enumerate(available_source_blocks), key=time_after_block)
                source_block_delay  = iodelay_of_block(source_block)

                new_target_time   = source_times[index] + source_block_delay
                target_time_delta = new_target_time - target_time
                assert target_time_delta >= 0

                target_terminator = target_block.terminator()
                if isinstance(target_terminator, ir.Interleave):
                    target_terminator.replace_with(ir.Branch(source_block))
                elif isinstance(target_terminator, (ir.Delay, ir.Branch)):
                    target_terminator.set_target(source_block)
                else:
                    assert False

                source_terminator = source_block.terminator()
                if isinstance(source_terminator, ir.Interleave):
                    source_terminator.replace_with(ir.Branch(source_terminator.target()))
                elif isinstance(source_terminator, ir.Branch):
                    pass
                elif isinstance(source_terminator, ir.BranchIf):
                    # Skip a delay-free loop/conditional
                    source_block = postdom_tree.immediate_dominator(source_block)
                    assert (source_block is not None)
                elif isinstance(source_terminator, ir.Return):
                    break
                elif isinstance(source_terminator, ir.Delay):
                    old_decomp = source_terminator.decomposition()
                    if is_pure_delay(old_decomp):
                        if target_time_delta > 0:
                            new_decomp_expr = ir.Constant(int(target_time_delta), builtins.TInt64())
                            new_decomp = ir.Builtin("delay_mu", [new_decomp_expr], builtins.TNone())
                            new_decomp.loc = old_decomp.loc

                            source_terminator.basic_block.insert(new_decomp, before=source_terminator)
                            source_terminator.interval = iodelay.Const(target_time_delta)
                            source_terminator.set_decomposition(new_decomp)
                        else:
                            source_terminator.replace_with(ir.Branch(source_terminator.target()))
                        old_decomp.erase()
                    else: # It's a call.
                        need_to_inline = len(source_blocks) > 1
                        if need_to_inline:
                            if old_decomp.static_target_function is None:
                                diag = diagnostic.Diagnostic("fatal",
                                    "it is not possible to interleave this function call within "
                                    "a 'with interleave:' statement because the compiler could not "
                                    "prove that the same function would always be called", {},
                                    old_decomp.loc)
                                self.engine.process(diag)

                            inline(old_decomp)
                            postdom_tree = domination.PostDominatorTree(func)
                            continue
                        elif target_time_delta > 0:
                            source_terminator.interval = iodelay.Const(target_time_delta)
                        else:
                            source_terminator.replace_with(ir.Branch(source_terminator.target()))
                elif isinstance(source_terminator, ir.Loop):
                    unroll(source_terminator)

                    postdom_tree = domination.PostDominatorTree(func)
                    continue
                else:
                    assert False

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
