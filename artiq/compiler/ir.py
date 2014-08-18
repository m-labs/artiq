from llvm import core as lc
from llvm import passes as lp

from artiq.compiler import ir_infer_types, ir_ast_body

def compile_function(module, env, funcdef):
	function_type = lc.Type.function(lc.Type.void(), [])
	function = module.add_function(function_type, funcdef.name)
	bb = function.append_basic_block("entry")
	builder = lc.Builder.new(bb)

	ns = ir_infer_types.infer_types(env, funcdef)
	for k, v in ns.items():
		v.create_alloca(builder, k)
	visitor = ir_ast_body.Visitor(env, ns, builder)
	visitor.visit_statements(funcdef.body)
	builder.ret_void()

def get_runtime_binary(env, funcdef):
	module = lc.Module.new("main")
	env.set_module(module)

	compile_function(module, funcdef)

	pass_manager = lp.PassManager.new()
	pass_manager.add(lp.PASS_MEM2REG)
	pass_manager.add(lp.PASS_INSTCOMBINE)
	pass_manager.add(lp.PASS_REASSOCIATE)
	pass_manager.add(lp.PASS_GVN)
	pass_manager.add(lp.PASS_SIMPLIFYCFG)
	pass_manager.run(module)

	return env.emit_object()
