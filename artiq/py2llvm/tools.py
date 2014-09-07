def is_terminated(basic_block):
	return basic_block.instructions and basic_block.instructions[-1].is_terminator
