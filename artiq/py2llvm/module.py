import llvmlite_or1k.ir as ll
import llvmlite_or1k.binding as llvm

from artiq.py2llvm import infer_types, ast_body, base_types, fractions, tools


class Module:
    def __init__(self, runtime=None):
        self.llvm_module = ll.Module("main")
        self.runtime = runtime

        if self.runtime is not None:
            self.runtime.init_module(self)
        fractions.init_module(self)

    def finalize(self):
        self.llvm_module_ref = llvm.parse_assembly(str(self.llvm_module))
        pmb = llvm.create_pass_manager_builder()
        pmb.opt_level = 2
        pm = llvm.create_module_pass_manager()
        pmb.populate(pm)
        pm.run(self.llvm_module_ref)

    def get_ee(self):
        self.finalize()
        tm = llvm.Target.from_default_triple().create_target_machine()
        ee = llvm.create_mcjit_compiler(self.llvm_module_ref, tm)
        ee.finalize_object()
        return ee

    def emit_object(self):
        self.finalize()
        return self.runtime.emit_object()

    def compile_function(self, func_def, param_types):
        ns = infer_types.infer_function_types(self.runtime, func_def, param_types)
        retval = ns["return"]

        function_type = ll.FunctionType(retval.get_llvm_type(),
            [ns[arg.arg].get_llvm_type() for arg in func_def.args.args])
        function = ll.Function(self.llvm_module, function_type, func_def.name)
        bb = function.append_basic_block("entry")
        builder = ll.IRBuilder()
        builder.position_at_end(bb)

        for arg_ast, arg_llvm in zip(func_def.args.args, function.args):
            arg_llvm.name = arg_ast.arg
        for k, v in ns.items():
            v.alloca(builder, k)
        for arg_ast, arg_llvm in zip(func_def.args.args, function.args):
            ns[arg_ast.arg].auto_store(builder, arg_llvm)

        visitor = ast_body.Visitor(self.runtime, ns, builder)
        visitor.visit_statements(func_def.body)

        if not tools.is_terminated(builder.basic_block):
            if isinstance(retval, base_types.VNone):
                builder.ret_void()
            else:
                builder.ret(retval.auto_load(builder))

        return function, retval
