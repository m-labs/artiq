from llvm import core as lc

syscall_map = {
	"rpc":				0,
	"rtio_set":			1,
	"rtio_sync":		2,
	"dds_program":		3,
}

class Environment:
	def emit_syscall(self, builder, syscall_name, args):
		syscall_nr = syscall_map[syscall_name]

		assert(0 <= syscall_nr <= 0xffff)
		# FIXME: replace with "l.sys syscall_nr" after the LLVM problems are fixed
		opcode = 0x20000000 | syscall_nr
		asm_string = "\n".join(".byte 0x{:02x}".format((opcode >> 8*i) & 0xff)
			for i in reversed(range(4)))

		sc_type = lc.Type.function(lc.Type.void(), [])
		asm = lc.InlineAsm.get(sc_type, asm_string, "")
		builder.call(asm, [])
