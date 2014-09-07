from llvm import core as lc
from llvm import passes as lp
from llvm import ee as le

from artiq.py2llvm import infer_types, ast_body, base_types, fractions, tools


class Module:
    def __init__(self, env=None):
        self.llvm_module = lc.Module.new("main")
        self.env = env

        if self.env is not None:
            self.env.init_module(self)
        fractions.init_module(self)

    def finalize(self):
        pass_manager = lp.PassManager.new()
        pass_manager.add(lp.PASS_MEM2REG)
        pass_manager.add(lp.PASS_INSTCOMBINE)
        pass_manager.add(lp.PASS_REASSOCIATE)
        pass_manager.add(lp.PASS_GVN)
        pass_manager.add(lp.PASS_SIMPLIFYCFG)
        pass_manager.run(self.llvm_module)

    def get_ee(self):
        self.finalize()
        return le.ExecutionEngine.new(self.llvm_module)

    def emit_object(self):
        self.finalize()
        return self.env.emit_object()

    def compile_function(self, funcdef, param_types):
        ns = infer_types.infer_function_types(self.env, funcdef, param_types)
        retval = ns["return"]

        function_type = lc.Type.function(retval.get_llvm_type(),
            [ns[arg.arg].get_llvm_type() for arg in funcdef.args.args])
        function = self.llvm_module.add_function(function_type, funcdef.name)
        bb = function.append_basic_block("entry")
        builder = lc.Builder.new(bb)

        for arg_ast, arg_llvm in zip(funcdef.args.args, function.args):
            arg_llvm.name = arg_ast.arg
        for k, v in ns.items():
            v.alloca(builder, k)
        for arg_ast, arg_llvm in zip(funcdef.args.args, function.args):
            ns[arg_ast.arg].set_ssa_value(builder, arg_llvm)

        visitor = ast_body.Visitor(self.env, ns, builder)
        visitor.visit_statements(funcdef.body)

        if not tools.is_terminated(builder.basic_block):
            if isinstance(retval, base_types.VNone):
                builder.ret_void()
            else:
                builder.ret(retval.get_ssa_value(builder))

        return function, retval
