"""
:func:`inline` inlines a call instruction in ARTIQ IR.
The call instruction must have a statically known callee,
it must be second to last in the basic block, and the basic
block must have exactly one successor.
"""

from .. import types, builtins, iodelay, ir

def inline(call_insn):
    assert isinstance(call_insn, ir.Call)
    assert call_insn.static_target_function is not None
    assert len(call_insn.basic_block.successors()) == 1
    assert call_insn.basic_block.index(call_insn) == \
                len(call_insn.basic_block.instructions) - 2

    value_map          = {}
    source_function    = call_insn.static_target_function
    target_function    = call_insn.basic_block.function
    target_predecessor = call_insn.basic_block
    target_successor   = call_insn.basic_block.successors()[0]

    if builtins.is_none(source_function.type.ret):
        target_return_phi = None
    else:
        target_return_phi = target_successor.prepend(ir.Phi(source_function.type.ret))

    closure = target_predecessor.insert(ir.GetAttr(call_insn.target_function(), '__closure__'),
                                        before=call_insn)
    for actual_arg, formal_arg in zip([closure] + call_insn.arguments(),
                                      source_function.arguments):
        value_map[formal_arg] = actual_arg

    for source_block in source_function.basic_blocks:
        target_block = ir.BasicBlock([], "i." + source_block.name)
        target_function.add(target_block)
        value_map[source_block] = target_block

    def mapper(value):
        if isinstance(value, ir.Constant):
            return value
        else:
            return value_map[value]

    for source_insn in source_function.instructions():
        target_block = value_map[source_insn.basic_block]
        if isinstance(source_insn, ir.Return):
            if target_return_phi is not None:
                target_return_phi.add_incoming(mapper(source_insn.value()), target_block)
            target_insn = ir.Branch(target_successor)
        elif isinstance(source_insn, ir.Phi):
            target_insn = ir.Phi()
        elif isinstance(source_insn, ir.Delay):
            target_insn = source_insn.copy(mapper)
            target_insn.interval = source_insn.interval.fold(call_insn.arg_exprs)
        elif isinstance(source_insn, ir.Loop):
            target_insn = source_insn.copy(mapper)
            target_insn.trip_count = source_insn.trip_count.fold(call_insn.arg_exprs)
        elif isinstance(source_insn, ir.Call):
            target_insn = source_insn.copy(mapper)
            target_insn.arg_exprs = \
                { arg: source_insn.arg_exprs[arg].fold(call_insn.arg_exprs)
                  for arg in source_insn.arg_exprs }
        else:
            target_insn = source_insn.copy(mapper)
        target_insn.name = "i." + source_insn.name
        value_map[source_insn] = target_insn
        target_block.append(target_insn)

    for source_insn in source_function.instructions():
        if isinstance(source_insn, ir.Phi):
            target_insn = value_map[source_insn]
            for block, value in source_insn.incoming():
                target_insn.add_incoming(value_map[value], value_map[block])

    target_predecessor.terminator().replace_with(ir.Branch(value_map[source_function.entry()]))
    if target_return_phi is not None:
        call_insn.replace_all_uses_with(target_return_phi)
    call_insn.erase()
