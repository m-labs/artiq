"""
:func:`unroll` unrolls a loop instruction in ARTIQ IR.
The loop's trip count must be constant.
The loop body must not have any control flow instructions
except for one branch back to the loop head.
The loop body must be executed if the condition to which
the instruction refers is true.
"""

from .. import types, builtins, iodelay, ir
from ..analyses import domination

def _get_body_blocks(root, limit):
    postorder = []

    visited = set()
    def visit(block):
        visited.add(block)
        for next_block in block.successors():
            if next_block not in visited and next_block is not limit:
                visit(next_block)
        postorder.append(block)

    visit(root)

    postorder.reverse()
    return postorder

def unroll(loop_insn):
    loop_head = loop_insn.basic_block
    function  = loop_head.function
    assert isinstance(loop_insn, ir.Loop)
    assert len(loop_head.predecessors()) == 2
    assert len(loop_insn.if_false().predecessors()) == 1
    assert iodelay.is_const(loop_insn.trip_count)

    trip_count = loop_insn.trip_count.fold().value
    if trip_count == 0:
        loop_insn.replace_with(ir.Branch(loop_insn.if_false()))
        return

    source_blocks = _get_body_blocks(loop_insn.if_true(), loop_head)
    source_indvar = loop_insn.induction_variable()
    source_tail   = loop_insn.if_false()
    unroll_target = loop_head
    for n in range(trip_count):
        value_map = {source_indvar: ir.Constant(n, source_indvar.type)}

        for source_block in source_blocks:
            target_block = ir.BasicBlock([], "u{}.{}".format(n, source_block.name))
            function.add(target_block)
            value_map[source_block] = target_block

        def mapper(value):
            if isinstance(value, ir.Constant):
                return value
            elif value in value_map:
                return value_map[value]
            else:
                return value

        for source_block in source_blocks:
            target_block = value_map[source_block]
            for source_insn in source_block.instructions:
                if isinstance(source_insn, ir.Phi):
                    target_insn = ir.Phi()
                else:
                    target_insn = source_insn.copy(mapper)
                    target_insn.name = "u{}.{}".format(n, source_insn.name)
                target_block.append(target_insn)
                value_map[source_insn] = target_insn

        for source_block in source_blocks:
            for source_insn in source_block.instructions:
                if isinstance(source_insn, ir.Phi):
                    target_insn = value_map[source_insn]
                    for block, value in source_insn.incoming():
                        target_insn.add_incoming(value_map[value], value_map[block])

        assert isinstance(unroll_target.terminator(), (ir.Branch, ir.Loop))
        unroll_target.terminator().replace_with(ir.Branch(value_map[source_blocks[0]]))
        unroll_target = value_map[source_blocks[-1]]

    assert isinstance(unroll_target.terminator(), ir.Branch)
    assert len(source_blocks[-1].successors()) == 1
    unroll_target.terminator().replace_with(ir.Branch(source_tail))

    for source_block in reversed(source_blocks):
        for source_insn in reversed(source_block.instructions):
            for use in set(source_insn.uses):
                if isinstance(use, ir.Phi):
                    assert use.basic_block == loop_head
                    use.remove_incoming_value(source_insn)
            source_insn.erase()

    for source_block in reversed(source_blocks):
        source_block.erase()
