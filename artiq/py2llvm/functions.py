from llvm import core as lc

from artiq.py2llvm import infer_types, ast_body, values, tools

def compile_function(module, env, funcdef, param_types):
    ns = infer_types.infer_function_types(env, funcdef, param_types)
    retval = ns["return"]

    function_type = lc.Type.function(retval.get_llvm_type(),
        [ns[arg.arg].get_llvm_type() for arg in funcdef.args.args])
    function = module.add_function(function_type, funcdef.name)
    bb = function.append_basic_block("entry")
    builder = lc.Builder.new(bb)

    for arg_ast, arg_llvm in zip(funcdef.args.args, function.args):
        arg_llvm.name = arg_ast.arg
    for k, v in ns.items():
        v.alloca(builder, k)
    for arg_ast, arg_llvm in zip(funcdef.args.args, function.args):
        ns[arg_ast.arg].set_ssa_value(builder, arg_llvm)

    visitor = ast_body.Visitor(env, ns, builder)
    visitor.visit_statements(funcdef.body)

    if not tools.is_terminated(builder.basic_block):
        if isinstance(retval, values.VNone):
            builder.ret_void()
        else:
            builder.ret(retval.get_ssa_value(builder))

    return function, retval
