"""
:class:`LLVMIRGenerator` transforms ARTIQ intermediate representation
into LLVM intermediate representation.
"""

import llvmlite.ir as ll
from pythonparser import ast
from .. import types, builtins, ir

class LLVMIRGenerator:
    def __init__(self, engine, module_name, context=ll.Context()):
        self.engine = engine
        self.llcontext = context
        self.llmodule = ll.Module(context=self.llcontext, name=module_name)
        self.llfunction = None
        self.llmap = {}
        self.fixups = []

    def llty_of_type(self, typ, bare=False, for_return=False):
        if types.is_tuple(typ):
            return ll.LiteralStructType([self.llty_of_type(eltty) for eltty in typ.find().elts])
        elif types.is_function(typ):
            envarg = ll.IntType(8).as_pointer()
            llty = ll.FunctionType(args=[envarg] +
                                        [self.llty_of_type(typ.args[arg])
                                         for arg in typ.args] +
                                        [self.llty_of_type(ir.TOption(typ.optargs[arg]))
                                         for arg in typ.optargs],
                                   return_type=self.llty_of_type(typ.ret, for_return=True))
            if bare:
                return llty
            else:
                return ll.LiteralStructType([envarg, llty.as_pointer()])
        elif builtins.is_none(typ):
            if for_return:
                return ll.VoidType()
            else:
                return ll.LiteralStructType([])
        elif builtins.is_bool(typ):
            return ll.IntType(1)
        elif builtins.is_int(typ):
            return ll.IntType(builtins.get_int_width(typ))
        elif builtins.is_float(typ):
            return ll.DoubleType()
        elif builtins.is_str(typ):
            return ll.IntType(8).as_pointer()
        elif builtins.is_list(typ):
            lleltty = self.llty_of_type(builtins.get_iterable_elt(typ))
            return ll.LiteralStructType([ll.IntType(32), lleltty.as_pointer()])
        elif builtins.is_range(typ):
            lleltty = self.llty_of_type(builtins.get_iterable_elt(typ))
            return ll.LiteralStructType([lleltty, lleltty, lleltty])
        elif builtins.is_exception(typ):
            # TODO: hack before EH is working
            return ll.LiteralStructType([])
        elif ir.is_basic_block(typ):
            return ll.LabelType()
        elif ir.is_option(typ):
            return ll.LiteralStructType([ll.IntType(1), self.llty_of_type(typ.params["inner"])])
        elif ir.is_environment(typ):
            llty = ll.LiteralStructType([self.llty_of_type(typ.params[name])
                                         for name in typ.params])
            if bare:
                return llty
            else:
                return llty.as_pointer()
        else:
            assert False

    def llconst_of_const(self, const):
        llty = self.llty_of_type(const.type)
        if const.value is None:
            return ll.Constant(llty, [])
        elif const.value is True:
            return ll.Constant(llty, True)
        elif const.value is False:
            return ll.Constant(llty, False)
        elif isinstance(const.value, (int, float)):
            return ll.Constant(llty, const.value)
        elif isinstance(const.value, str):
            as_bytes = (const.value + '\0').encode('utf-8')
            llstrty = ll.ArrayType(ll.IntType(8), len(as_bytes))
            llconst = ll.GlobalVariable(self.llmodule, llstrty,
                                        name=self.llmodule.get_unique_name("str"))
            llconst.global_constant = True
            llconst.unnamed_addr = True
            llconst.linkage = 'internal'
            llconst.initializer = ll.Constant(llstrty, bytearray(as_bytes))
            return llconst.bitcast(ll.IntType(8).as_pointer())
        else:
            assert False

    def map(self, value):
        if isinstance(value, (ir.Argument, ir.Instruction, ir.BasicBlock)):
            return self.llmap[value]
        elif isinstance(value, ir.Constant):
            return self.llconst_of_const(value)
        elif isinstance(value, ir.Function):
            llfun = self.llmodule.get_global(value.name)
            if llfun is None:
                return ll.Function(self.llmodule, self.llty_of_type(value.type, bare=True),
                                   value.name)
            else:
                return llfun
        else:
            assert False

    def process(self, functions):
        for func in functions:
            self.process_function(func)

    def process_function(self, func):
        try:
            self.llfunction = self.llmodule.get_global(func.name)
            if self.llfunction is None:
                llargtys = []
                for arg in func.arguments:
                    llargtys.append(self.llty_of_type(arg.type))
                llfunty = ll.FunctionType(args=llargtys,
                                          return_type=self.llty_of_type(func.type.ret, for_return=True))
                self.llfunction = ll.Function(self.llmodule, llfunty, func.name)
                self.llfunction.linkage = 'internal'

            self.llmap = {}
            self.llbuilder = ll.IRBuilder()
            self.fixups = []

            # First, map arguments.
            for arg, llarg in zip(func.arguments, self.llfunction.args):
                self.llmap[arg] = llarg

            # Second, create all basic blocks.
            for block in func.basic_blocks:
                llblock = self.llfunction.append_basic_block(block.name)
                self.llmap[block] = llblock

            # Third, translate all instructions.
            for block in func.basic_blocks:
                self.llbuilder.position_at_end(self.llmap[block])
                for insn in block.instructions:
                    llinsn = getattr(self, "process_" + type(insn).__name__)(insn)
                    assert llinsn is not None
                    self.llmap[insn] = llinsn

            # Fourth, fixup phis.
            for fixup in self.fixups:
                fixup()
        finally:
            self.llfunction = None
            self.llmap = None
            self.fixups = []

    def process_Phi(self, insn):
        llinsn = self.llbuilder.phi(self.llty_of_type(insn.type), name=insn.name)
        def fixup():
            for value, block in insn.incoming():
                llinsn.add_incoming(self.map(value), self.map(block))
        self.fixups.append(fixup)
        return llinsn

    def process_Alloc(self, insn):
        if ir.is_environment(insn.type):
            return self.llbuilder.alloca(self.llty_of_type(insn.type, bare=True),
                                         name=insn.name)
        elif builtins.is_list(insn.type):
            llsize = self.map(insn.operands[0])
            llvalue = ll.Constant(self.llty_of_type(insn.type), ll.Undefined)
            llvalue = self.llbuilder.insert_value(llvalue, llsize, 0)
            llalloc = self.llbuilder.alloca(self.llty_of_type(builtins.get_iterable_elt(insn.type)),
                                            size=llsize)
            llvalue = self.llbuilder.insert_value(llvalue, llalloc, 1, name=insn.name)
            return llvalue
        elif builtins.is_allocated(insn.type):
            assert False
        else: # immutable
            llvalue = ll.Constant(self.llty_of_type(insn.type), ll.Undefined)
            for index, elt in enumerate(insn.operands):
                llvalue = self.llbuilder.insert_value(llvalue, self.map(elt), index)
            llvalue.name = insn.name
            return llvalue

    def llindex(self, index):
        return ll.Constant(ll.IntType(32), index)

    def llptr_to_var(self, llenv, env_ty, var_name):
        if var_name in env_ty.params:
            var_index = list(env_ty.params.keys()).index(var_name)
            return self.llbuilder.gep(llenv, [self.llindex(0), self.llindex(var_index)])
        else:
            outer_index = list(env_ty.params.keys()).index(".outer")
            llptr = self.llbuilder.gep(llenv, [self.llindex(0), self.llindex(outer_index)])
            llouterenv = self.llbuilder.load(llptr)
            return self.llptr_to_var(llouterenv, env_ty.params[".outer"], var_name)

    def process_GetLocal(self, insn):
        env = insn.environment()
        llptr = self.llptr_to_var(self.map(env), env.type, insn.var_name)
        return self.llbuilder.load(llptr)

    def process_SetLocal(self, insn):
        env = insn.environment()
        llptr = self.llptr_to_var(self.map(env), env.type, insn.var_name)
        llvalue = self.map(insn.value())
        if llptr.type.pointee != llvalue.type:
            # The environment argument is an i8*, so that all closures can
            # unify with each other regardless of environment type or size.
            # We fixup the type on assignment into the ".outer" slot.
            assert isinstance(insn.value(), ir.EnvironmentArgument)
            llvalue = self.llbuilder.bitcast(llvalue, llptr.type.pointee)
        return self.llbuilder.store(llvalue, llptr)

    def attr_index(self, insn):
        return list(insn.object().type.attributes.keys()).index(insn.attr)

    def process_GetAttr(self, insn):
        if types.is_tuple(insn.object().type):
            return self.llbuilder.extract_value(self.map(insn.object()), self.attr_index(insn),
                                                name=insn.name)
        elif not builtins.is_allocated(insn.object().type):
            return self.llbuilder.extract_value(self.map(insn.object()), self.attr_index(insn),
                                                name=insn.name)
        else:
            llptr = self.llbuilder.gep(self.map(insn.object()),
                                       [self.llindex(0), self.llindex(self.attr_index(insn))],
                                       name=insn.name)
            return self.llbuilder.load(llptr)

    def process_SetAttr(self, insn):
        assert builtins.is_allocated(insns.object().type)
        llptr = self.llbuilder.gep(self.map(insn.object()),
                                   [self.llindex(0), self.llindex(self.attr_index(insn))],
                                   name=insn.name)
        return self.llbuilder.store(llptr, self.map(insn.value()))

    def process_GetElem(self, insn):
        llelts = self.llbuilder.extract_value(self.map(insn.list()), 1)
        llelt = self.llbuilder.gep(llelts, [self.map(insn.index())],
                                   inbounds=True)
        return self.llbuilder.load(llelt)

    def process_SetElem(self, insn):
        llelts = self.llbuilder.extract_value(self.map(insn.list()), 1)
        llelt = self.llbuilder.gep(llelts, [self.map(insn.index())],
                                   inbounds=True)
        return self.llbuilder.store(self.map(insn.value()), llelt)

    def process_Coerce(self, insn):
        typ, value_typ = insn.type, insn.value().type
        if builtins.is_int(typ) and builtins.is_float(value_typ):
            return self.llbuilder.fptosi(self.map(insn.value()), self.llty_of_type(typ),
                                         name=insn.name)
        elif builtins.is_float(typ) and builtins.is_int(value_typ):
            return self.llbuilder.sitofp(self.map(insn.value()), self.llty_of_type(typ),
                                         name=insn.name)
        elif builtins.is_int(typ) and builtins.is_int(value_typ):
            if builtins.get_int_width(typ) > builtins.get_int_width(value_typ):
                return self.llbuilder.sext(self.map(insn.value()), self.llty_of_type(typ),
                                           name=insn.name)
            else: # builtins.get_int_width(typ) < builtins.get_int_width(value_typ):
                return self.llbuilder.trunc(self.map(insn.value()), self.llty_of_type(typ),
                                            name=insn.name)
        else:
            assert False

    def process_Arith(self, insn):
        if isinstance(insn.op, ast.Add):
            if builtins.is_float(insn.type):
                return self.llbuilder.fadd(self.map(insn.lhs()), self.map(insn.rhs()),
                                           name=insn.name)
            else:
                return self.llbuilder.add(self.map(insn.lhs()), self.map(insn.rhs()),
                                          name=insn.name)
        elif isinstance(insn.op, ast.Sub):
            if builtins.is_float(insn.type):
                return self.llbuilder.fsub(self.map(insn.lhs()), self.map(insn.rhs()),
                                           name=insn.name)
            else:
                return self.llbuilder.sub(self.map(insn.lhs()), self.map(insn.rhs()),
                                          name=insn.name)
        elif isinstance(insn.op, ast.Mult):
            if builtins.is_float(insn.type):
                return self.llbuilder.fmul(self.map(insn.lhs()), self.map(insn.rhs()),
                                           name=insn.name)
            else:
                return self.llbuilder.mul(self.map(insn.lhs()), self.map(insn.rhs()),
                                          name=insn.name)
        elif isinstance(insn.op, ast.Div):
            if builtins.is_float(insn.lhs().type):
                return self.llbuilder.fdiv(self.map(insn.lhs()), self.map(insn.rhs()),
                                           name=insn.name)
            else:
                lllhs = self.llbuilder.sitofp(self.map(insn.lhs()), self.llty_of_type(insn.type))
                llrhs = self.llbuilder.sitofp(self.map(insn.rhs()), self.llty_of_type(insn.type))
                return self.llbuilder.fdiv(lllhs, llrhs,
                                           name=insn.name)
        elif isinstance(insn.op, ast.FloorDiv):
            if builtins.is_float(insn.type):
                llvalue = self.llbuilder.fdiv(self.map(insn.lhs()), self.map(insn.rhs()))
                llfnty = ll.FunctionType(ll.DoubleType(), [ll.DoubleType()])
                llfn = ll.Function(self.llmodule, llfnty, "llvm.round.f64")
                return self.llbuilder.call(llfn, [llvalue],
                                           name=insn.name)
            else:
                return self.llbuilder.sdiv(self.map(insn.lhs()), self.map(insn.rhs()),
                                           name=insn.name)
        elif isinstance(insn.op, ast.Mod):
            if builtins.is_float(insn.type):
                return self.llbuilder.frem(self.map(insn.lhs()), self.map(insn.rhs()),
                                           name=insn.name)
            else:
                return self.llbuilder.srem(self.map(insn.lhs()), self.map(insn.rhs()),
                                           name=insn.name)
        elif isinstance(insn.op, ast.Pow):
            if builtins.is_float(insn.type):
                llfnty = ll.FunctionType(ll.DoubleType(), [ll.DoubleType(), ll.DoubleType()])
                llfn = ll.Function(self.llmodule, llfnty, "llvm.pow.f64")
                return self.llbuilder.call(llfn, [self.map(insn.lhs()), self.map(insn.rhs())],
                                           name=insn.name)
            else:
                llrhs = self.llbuilder.trunc(self.map(insn.rhs()), ll.IntType(32))
                llfnty = ll.FunctionType(ll.DoubleType(), [ll.DoubleType(), ll.IntType(32)])
                llfn = ll.Function(self.llmodule, llfnty, "llvm.powi.f64")
                llvalue = self.llbuilder.call(llfn, [self.map(insn.lhs()), llrhs])
                return self.llbuilder.fptosi(llvalue, self.llty_of_type(insn.type),
                                             name=insn.name)
        elif isinstance(insn.op, ast.LShift):
            return self.llbuilder.shl(self.map(insn.lhs()), self.map(insn.rhs()),
                                      name=insn.name)
        elif isinstance(insn.op, ast.RShift):
            return self.llbuilder.ashr(self.map(insn.lhs()), self.map(insn.rhs()),
                                       name=insn.name)
        elif isinstance(insn.op, ast.BitAnd):
            return self.llbuilder.and_(self.map(insn.lhs()), self.map(insn.rhs()),
                                       name=insn.name)
        elif isinstance(insn.op, ast.BitOr):
            return self.llbuilder.or_(self.map(insn.lhs()), self.map(insn.rhs()),
                                      name=insn.name)
        elif isinstance(insn.op, ast.BitXor):
            return self.llbuilder.xor(self.map(insn.lhs()), self.map(insn.rhs()),
                                      name=insn.name)
        else:
            assert False

    def process_Compare(self, insn):
        if isinstance(insn.op, ast.Eq):
            op = '=='
        elif isinstance(insn.op, ast.NotEq):
            op = '!='
        elif isinstance(insn.op, ast.Gt):
            op = '>'
        elif isinstance(insn.op, ast.GtE):
            op = '>='
        elif isinstance(insn.op, ast.Lt):
            op = '<'
        elif isinstance(insn.op, ast.LtE):
            op = '<='
        else:
            assert False

        if builtins.is_float(insn.lhs().type):
            return self.llbuilder.fcmp_ordered(op, self.map(insn.lhs()), self.map(insn.rhs()),
                                               name=insn.name)
        else:
            return self.llbuilder.icmp_signed(op, self.map(insn.lhs()), self.map(insn.rhs()),
                                              name=insn.name)

    def process_Builtin(self, insn):
        if insn.op == "nop":
            fn = ll.Function(self.llmodule, ll.FunctionType(ll.VoidType(), []), "llvm.donothing")
            return self.llbuilder.call(fn, [])
        elif insn.op == "unwrap":
            optarg, default = map(self.map, insn.operands)
            has_arg = self.llbuilder.extract_value(optarg, 0)
            arg = self.llbuilder.extract_value(optarg, 1)
            return self.llbuilder.select(has_arg, arg, default,
                                         name=insn.name)
        elif insn.op == "round":
            llfnty = ll.FunctionType(ll.DoubleType(), [ll.DoubleType()])
            llfn = ll.Function(self.llmodule, llfnty, "llvm.round.f64")
            return self.llbuilder.call(llfn, [llvalue],
                                       name=insn.name)
        elif insn.op == "globalenv":
            def get_outer(llenv, env_ty):
                if ".outer" in env_ty.params:
                    outer_index = list(env_ty.params.keys()).index(".outer")
                    llptr = self.llbuilder.gep(llenv, [self.llindex(0), self.llindex(outer_index)])
                    llouterenv = self.llbuilder.load(llptr)
                    return self.llptr_to_var(llouterenv, env_ty.params[".outer"], var_name)
                else:
                    return llenv

            env, = insn.operands
            return get_outer(self.map(env), env.type)
        elif insn.op == "len":
            lst, = insn.operands
            return self.llbuilder.extract_value(self.map(lst), 0)
        # elif insn.op == "exncast":
        else:
            assert False

    def process_Closure(self, insn):
        llvalue = ll.Constant(self.llty_of_type(insn.target_function.type), ll.Undefined)
        llenv = self.llbuilder.bitcast(self.map(insn.environment()), ll.IntType(8).as_pointer())
        llvalue = self.llbuilder.insert_value(llvalue, llenv, 0)
        llvalue = self.llbuilder.insert_value(llvalue, self.map(insn.target_function), 1,
                                              name=insn.name)
        return llvalue

    def process_Call(self, insn):
        llclosure, llargs = self.map(insn.target_function()), map(self.map, insn.arguments())
        llenv = self.llbuilder.extract_value(llclosure, 0)
        llfun = self.llbuilder.extract_value(llclosure, 1)
        return self.llbuilder.call(llfun, [llenv] + list(llargs),
                                   name=insn.name)

    def process_Select(self, insn):
        return self.llbuilder.select(self.map(insn.cond()),
                                     self.map(insn.lhs()), self.map(insn.rhs()))

    def process_Branch(self, insn):
        return self.llbuilder.branch(self.map(insn.target()))

    def process_BranchIf(self, insn):
        return self.llbuilder.cbranch(self.map(insn.condition()),
                                      self.map(insn.if_true()), self.map(insn.if_false()))

    # def process_IndirectBranch(self, insn):
    #     pass

    def process_Return(self, insn):
        if builtins.is_none(insn.value().type):
            return self.llbuilder.ret_void()
        else:
            return self.llbuilder.ret(self.llmap[insn.value()])

    def process_Unreachable(self, insn):
        return self.llbuilder.unreachable()

    def process_Raise(self, insn):
        # TODO: hack before EH is working
        llfnty = ll.FunctionType(ll.VoidType(), [])
        llfn = ll.Function(self.llmodule, llfnty, "llvm.abort")
        llinsn = self.llbuilder.call(llfn, [],
                                     name=insn.name)
        self.llbuilder.unreachable()
        return llinsn

    # def process_Invoke(self, insn):
    #     pass

    # def process_LandingPad(self, insn):
    #     pass

