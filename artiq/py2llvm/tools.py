from llvm import passes as lp

def is_terminated(basic_block):
	return basic_block.instructions and basic_block.instructions[-1].is_terminator

def add_common_passes(pass_manager):
    pass_manager.add(lp.PASS_MEM2REG)
    pass_manager.add(lp.PASS_INSTCOMBINE)
    pass_manager.add(lp.PASS_REASSOCIATE)
    pass_manager.add(lp.PASS_GVN)
    pass_manager.add(lp.PASS_SIMPLIFYCFG)
