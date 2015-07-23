import llvmlite_or1k.ir as ll

def is_terminated(basic_block):
	return (basic_block.instructions
            and isinstance(basic_block.instructions[-1], ll.Terminator))
