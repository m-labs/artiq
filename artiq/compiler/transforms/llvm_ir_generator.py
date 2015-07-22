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

    def llbuiltin(self, name):
        llfun = self.llmodule.get_global(name)
        if llfun is not None:
            return llfun

        if name in "llvm.donothing":
            llty = ll.FunctionType(ll.VoidType(), [])
        elif name in "llvm.trap":
            llty = ll.FunctionType(ll.VoidType(), [])
        elif name == "llvm.floor.f64":
            llty = ll.FunctionType(ll.DoubleType(), [ll.DoubleType()])
        elif name == "llvm.round.f64":
            llty = ll.FunctionType(ll.DoubleType(), [ll.DoubleType()])
        elif name == "llvm.pow.f64":
            llty = ll.FunctionType(ll.DoubleType(), [ll.DoubleType(), ll.DoubleType()])
        elif name == "llvm.powi.f64":
            llty = ll.FunctionType(ll.DoubleType(), [ll.DoubleType(), ll.IntType(32)])
        elif name == "llvm.copysign.f64":
            llty = ll.FunctionType(ll.DoubleType(), [ll.DoubleType(), ll.DoubleType()])
        elif name == "printf":
            llty = ll.FunctionType(ll.VoidType(), [ll.IntType(8).as_pointer()], var_arg=True)
        else:
            assert False
        return ll.Function(self.llmodule, llty, name)

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

        return self.llmodule

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
        elif ir.is_option(insn.type):
            if len(insn.operands) == 0: # empty
                llvalue = ll.Constant(self.llty_of_type(insn.type), ll.Undefined)
                return self.llbuilder.insert_value(llvalue, ll.Constant(ll.IntType(1), False), 0,
                                                   name=insn.name)
            elif len(insn.operands) == 1: # full
                llvalue = ll.Constant(self.llty_of_type(insn.type), ll.Undefined)
                llvalue = self.llbuilder.insert_value(llvalue, ll.Constant(ll.IntType(1), True), 0)
                return self.llbuilder.insert_value(llvalue, self.map(insn.operands[0]), 1,
                                                   name=insn.name)
            else:
                assert False
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
            return self.llbuilder.extract_value(self.map(insn.object()), insn.attr,
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
            else: # builtins.get_int_width(typ) <= builtins.get_int_width(value_typ):
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
                return self.llbuilder.call(self.llbuiltin("llvm.floor.f64"), [llvalue],
                                           name=insn.name)
            else:
                return self.llbuilder.sdiv(self.map(insn.lhs()), self.map(insn.rhs()),
                                           name=insn.name)
        elif isinstance(insn.op, ast.Mod):
            # Python only has the modulo operator, LLVM only has the remainder
            if builtins.is_float(insn.type):
                llvalue = self.llbuilder.frem(self.map(insn.lhs()), self.map(insn.rhs()))
                return self.llbuilder.call(self.llbuiltin("llvm.copysign.f64"),
                                           [llvalue, self.map(insn.rhs())],
                                           name=insn.name)
            else:
                lllhs, llrhs = map(self.map, (insn.lhs(), insn.rhs()))
                llxorsign = self.llbuilder.and_(self.llbuilder.xor(lllhs, llrhs),
                                                ll.Constant(lllhs.type, 1 << lllhs.type.width - 1))
                llnegate = self.llbuilder.icmp_unsigned('!=',
                                                        llxorsign, ll.Constant(llxorsign.type, 0))
                llvalue = self.llbuilder.srem(lllhs, llrhs)
                llnegvalue = self.llbuilder.sub(ll.Constant(llvalue.type, 0), llvalue)
                return self.llbuilder.select(llnegate, llnegvalue, llvalue)
        elif isinstance(insn.op, ast.Pow):
            if builtins.is_float(insn.type):
                return self.llbuilder.call(self.llbuiltin("llvm.pow.f64"),
                                           [self.map(insn.lhs()), self.map(insn.rhs())],
                                           name=insn.name)
            else:
                lllhs = self.llbuilder.sitofp(self.map(insn.lhs()), ll.DoubleType())
                llrhs = self.llbuilder.trunc(self.map(insn.rhs()), ll.IntType(32))
                llvalue = self.llbuilder.call(self.llbuiltin("llvm.powi.f64"), [lllhs, llrhs])
                return self.llbuilder.fptosi(llvalue, self.llty_of_type(insn.type),
                                             name=insn.name)
        elif isinstance(insn.op, ast.LShift):
            lllhs, llrhs = map(self.map, (insn.lhs(), insn.rhs()))
            llrhs_max = ll.Constant(llrhs.type, builtins.get_int_width(insn.lhs().type))
            llrhs_overflow = self.llbuilder.icmp_signed('>=', llrhs, llrhs_max)
            llvalue_zero = ll.Constant(lllhs.type, 0)
            llvalue = self.llbuilder.shl(lllhs, llrhs)
            return self.llbuilder.select(llrhs_overflow, llvalue_zero, llvalue,
                                         name=insn.name)
        elif isinstance(insn.op, ast.RShift):
            lllhs, llrhs = map(self.map, (insn.lhs(), insn.rhs()))
            llrhs_max = ll.Constant(llrhs.type, builtins.get_int_width(insn.lhs().type) - 1)
            llrhs_overflow = self.llbuilder.icmp_signed('>', llrhs, llrhs_max)
            llvalue = self.llbuilder.ashr(lllhs, llrhs)
            llvalue_max = self.llbuilder.ashr(lllhs, llrhs_max) # preserve sign bit
            return self.llbuilder.select(llrhs_overflow, llvalue_max, llvalue,
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
        if isinstance(insn.op, (ast.Eq, ast.Is)):
            op = '=='
        elif isinstance(insn.op, (ast.NotEq, ast.IsNot)):
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

        lllhs, llrhs = map(self.map, (insn.lhs(), insn.rhs()))
        assert lllhs.type == llrhs.type

        if isinstance(lllhs.type, ll.IntType):
            return self.llbuilder.icmp_signed(op, lllhs, llrhs,
                                                name=insn.name)
        elif isinstance(lllhs.type, ll.PointerType):
            return self.llbuilder.icmp_unsigned(op, lllhs, llrhs,
                                                name=insn.name)
        elif isinstance(lllhs.type, (ll.FloatType, ll.DoubleType)):
            return self.llbuilder.fcmp_ordered(op, lllhs, llrhs,
                                               name=insn.name)
        elif isinstance(lllhs.type, ll.LiteralStructType):
            # Compare aggregates (such as lists or ranges) element-by-element.
            llvalue = ll.Constant(ll.IntType(1), True)
            for index in range(len(lllhs.type.elements)):
                lllhselt = self.llbuilder.extract_value(lllhs, index)
                llrhselt = self.llbuilder.extract_value(llrhs, index)
                llresult = self.llbuilder.icmp_unsigned('==', lllhselt, llrhselt)
                llvalue  = self.llbuilder.select(llresult, llvalue,
                                                 ll.Constant(ll.IntType(1), False))
            return self.llbuilder.icmp_unsigned(op, llvalue, ll.Constant(ll.IntType(1), True),
                                                name=insn.name)
        else:
            print(lllhs, llrhs)
            assert False

    def process_Builtin(self, insn):
        if insn.op == "nop":
            return self.llbuilder.call(self.llbuiltin("llvm.donothing"), [])
        if insn.op == "abort":
            return self.llbuilder.call(self.llbuiltin("llvm.trap"), [])
        elif insn.op == "is_some":
            lloptarg = self.map(insn.operands[0])
            return self.llbuilder.extract_value(lloptarg, 0,
                                                name=insn.name)
        elif insn.op == "unwrap":
            lloptarg = self.map(insn.operands[0])
            return self.llbuilder.extract_value(lloptarg, 1,
                                                name=insn.name)
        elif insn.op == "unwrap_or":
            lloptarg, lldefault = map(self.map, insn.operands)
            llhas_arg = self.llbuilder.extract_value(lloptarg, 0)
            llarg = self.llbuilder.extract_value(lloptarg, 1)
            return self.llbuilder.select(llhas_arg, llarg, lldefault,
                                         name=insn.name)
        elif insn.op == "round":
            llarg = self.map(insn.operands[0])
            llvalue = self.llbuilder.call(self.llbuiltin("llvm.round.f64"), [llarg])
            return self.llbuilder.fptosi(llvalue, self.llty_of_type(insn.type),
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
        elif insn.op == "printf":
            # We only get integers, floats, pointers and strings here.
            llargs = map(self.map, insn.operands)
            return self.llbuilder.call(self.llbuiltin("printf"), llargs,
                                       name=insn.name)
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
        return self.llbuilder.select(self.map(insn.condition()),
                                     self.map(insn.if_true()), self.map(insn.if_false()))

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
        llinsn = self.llbuilder.call(self.llbuiltin("llvm.trap"), [],
                                     name=insn.name)
        self.llbuilder.unreachable()
        return llinsn

    # def process_Invoke(self, insn):
    #     pass

    # def process_LandingPad(self, insn):
    #     pass

