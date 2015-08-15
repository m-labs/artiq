"""
:class:`LLVMIRGenerator` transforms ARTIQ intermediate representation
into LLVM intermediate representation.
"""

import os
from pythonparser import ast, diagnostic
from llvmlite_artiq import ir as ll
from .. import types, builtins, ir


llvoid     = ll.VoidType()
lli1       = ll.IntType(1)
lli8       = ll.IntType(8)
lli32      = ll.IntType(32)
lldouble   = ll.DoubleType()
llptr      = ll.IntType(8).as_pointer()
llmetadata = ll.MetaData()


DW_LANG_Python         = 0x0014
DW_TAG_compile_unit    = 17
DW_TAG_subroutine_type = 21
DW_TAG_file_type       = 41
DW_TAG_subprogram      = 46

def memoize(generator):
    def memoized(self, *args):
        result = self.cache.get((generator,) + args, None)
        if result is None:
            return generator(self, *args)
        else:
            return result
    return memoized

class DebugInfoEmitter:
    def __init__(self, llmodule):
        self.llmodule = llmodule
        self.cache = {}
        self.subprograms = []

    def emit(self, operands):
        def map_operand(operand):
            if operand is None:
                return ll.Constant(llmetadata, None)
            elif isinstance(operand, str):
                return ll.MetaDataString(self.llmodule, operand)
            elif isinstance(operand, bool):
                return ll.Constant(lli1, operand)
            elif isinstance(operand, int):
                return ll.Constant(lli32, operand)
            elif isinstance(operand, (list, tuple)):
                return self.emit(operand)
            elif isinstance(operand, ll.Value):
                return operand
            else:
                print(operand)
                assert False
        return self.llmodule.add_metadata(list(map(map_operand, operands)))

    @memoize
    def emit_filename(self, source_buffer):
        source_dir, source_file = os.path.split(source_buffer.name)
        return self.emit([source_file, source_dir])

    @memoize
    def emit_compile_unit(self, source_buffer, llsubprograms):
        return self.emit([
            DW_TAG_compile_unit,
            self.emit_filename(source_buffer),    # filename
            DW_LANG_Python,                       # source language
            "ARTIQ",                              # producer
            False,                                # optimized?
            "",                                   # linker flags
            0,                                    # runtime version
            [],                                   # enum types
            [],                                   # retained types
            llsubprograms,                        # subprograms
            [],                                   # global variables
            [],                                   # imported entities
            "",                                   # split debug filename
            2,                                    # kind (full=1, lines only=2)
        ])

    @memoize
    def emit_file(self, source_buffer):
        return self.emit([
            DW_TAG_file_type,
            self.emit_filename(source_buffer),    # filename
        ])

    @memoize
    def emit_subroutine_type(self, typ):
        return self.emit([
            DW_TAG_subroutine_type,
            None,                                 # filename
            None,                                 # context descriptor
            "",                                   # name
            0,                                    # line number
            0,                                    # (i64) size in bits
            0,                                    # (i64) alignment in bits
            0,                                    # (i64) offset in bits
            0,                                    # flags
            None,                                 # derived from
            [None],                               # members
            0,                                    # runtime languages
            None,                                 # base type with vtable pointer
            None,                                 # template parameters
            None                                  # unique identifier
        ])

    @memoize
    def emit_subprogram(self, func, llfunc):
        source_buffer = func.loc.source_buffer
        display_name = "{}{}".format(func.name, types.TypePrinter().name(func.type))
        subprogram = self.emit([
            DW_TAG_subprogram,
            self.emit_filename(source_buffer),    # filename
            self.emit_file(source_buffer),        # context descriptor
            func.name,                            # name
            display_name,                         # display name
            llfunc.name,                          # linkage name
            func.loc.line(),                      # line number where defined
            self.emit_subroutine_type(func.type), # type descriptor
            func.is_internal,                     # local to compile unit?
            True,                                 # global is defined in the compile unit?
            0,                                    # virtuality
            0,                                    # index into a virtual function
            None,                                 # base type with vtable pointer
            0,                                    # flags
            False,                                # optimized?
            llfunc,                               # LLVM function
            None,                                 # template parameters
            None,                                 # function declaration descriptor
            [],                                   # function variables
            func.loc.line(),                      # line number where scope begins
        ])
        self.subprograms.append(subprogram)
        return subprogram

    @memoize
    def emit_loc(self, loc, scope, inlined_scope=None):
        return self.emit([
            loc.line(),                           # line
            loc.column(),                         # column
            scope,                                # scope
            inlined_scope,                        # inlined scope
        ])

    def finalize(self, source_buffer):
        llident = self.llmodule.add_named_metadata('llvm.ident')
        llident.add(self.emit(["ARTIQ"]))

        llflags = self.llmodule.add_named_metadata('llvm.module.flags')
        llflags.add(self.emit([2, "Debug Info Version", 1]))

        llcompile_units = self.llmodule.add_named_metadata('llvm.dbg.cu')
        llcompile_units.add(self.emit_compile_unit(source_buffer, tuple(self.subprograms)))


class LLVMIRGenerator:
    def __init__(self, engine, module_name, target):
        self.engine = engine
        self.target = target
        self.llcontext = target.llcontext
        self.llmodule = ll.Module(context=self.llcontext, name=module_name)
        self.llmodule.triple = target.triple
        self.llmodule.data_layout = target.data_layout
        self.llfunction = None
        self.llmap = {}
        self.phis = []
        self.debug_info_emitter = DebugInfoEmitter(self.llmodule)

    def llty_of_type(self, typ, bare=False, for_return=False):
        typ = typ.find()
        if types.is_tuple(typ):
            return ll.LiteralStructType([self.llty_of_type(eltty) for eltty in typ.elts])
        elif types.is_rpc_function(typ) or types.is_c_function(typ):
            if for_return:
                return llvoid
            else:
                return ll.LiteralStructType([])
        elif types.is_function(typ):
            envarg = llptr
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
                return llvoid
            else:
                return ll.LiteralStructType([])
        elif builtins.is_bool(typ):
            return lli1
        elif builtins.is_int(typ):
            return ll.IntType(builtins.get_int_width(typ))
        elif builtins.is_float(typ):
            return lldouble
        elif builtins.is_str(typ) or ir.is_exn_typeinfo(typ):
            return llptr
        elif builtins.is_list(typ):
            lleltty = self.llty_of_type(builtins.get_iterable_elt(typ))
            return ll.LiteralStructType([lli32, lleltty.as_pointer()])
        elif builtins.is_range(typ):
            lleltty = self.llty_of_type(builtins.get_iterable_elt(typ))
            return ll.LiteralStructType([lleltty, lleltty, lleltty])
        elif ir.is_basic_block(typ):
            return llptr
        elif ir.is_option(typ):
            return ll.LiteralStructType([lli1, self.llty_of_type(typ.params["inner"])])
        elif ir.is_environment(typ):
            llty = ll.LiteralStructType([self.llty_of_type(typ.params[name])
                                         for name in typ.params])
            if bare:
                return llty
            else:
                return llty.as_pointer()
        else: # Catch-all for exceptions and custom classes
            if builtins.is_exception(typ):
                name = 'Exception' # they all share layout
            else:
                name = typ.name

            llty = self.llcontext.get_identified_type(name)
            if llty.elements is None:
                llty.elements = [self.llty_of_type(attrtyp)
                                 for attrtyp in typ.attributes.values()]

            if bare or not builtins.is_allocated(typ):
                return llty
            else:
                return llty.as_pointer()

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
        elif isinstance(const.value, (str, bytes)):
            if isinstance(const.value, str):
                assert "\0" not in const.value
                as_bytes = (const.value + "\0").encode("utf-8")
            else:
                as_bytes = const.value

            if ir.is_exn_typeinfo(const.type):
                # Exception typeinfo; should be merged with identical others
                name = "__artiq_exn_" + const.value
                linkage = "linkonce"
                unnamed_addr = False
            else:
                # Just a string
                name = self.llmodule.get_unique_name("str")
                linkage = "private"
                unnamed_addr = True

            llconst = self.llmodule.get_global(name)
            if llconst is None:
                llstrty = ll.ArrayType(lli8, len(as_bytes))
                llconst = ll.GlobalVariable(self.llmodule, llstrty, name)
                llconst.global_constant = True
                llconst.initializer = ll.Constant(llstrty, bytearray(as_bytes))
                llconst.linkage = linkage
                llconst.unnamed_addr = unnamed_addr

            return llconst.bitcast(llptr)
        else:
            assert False

    def llbuiltin(self, name):
        llfun = self.llmodule.get_global(name)
        if llfun is not None:
            return llfun

        if name in "llvm.donothing":
            llty = ll.FunctionType(llvoid, [])
        elif name in "llvm.trap":
            llty = ll.FunctionType(llvoid, [])
        elif name == "llvm.floor.f64":
            llty = ll.FunctionType(lldouble, [lldouble])
        elif name == "llvm.round.f64":
            llty = ll.FunctionType(lldouble, [lldouble])
        elif name == "llvm.pow.f64":
            llty = ll.FunctionType(lldouble, [lldouble, lldouble])
        elif name == "llvm.powi.f64":
            llty = ll.FunctionType(lldouble, [lldouble, lli32])
        elif name == "llvm.copysign.f64":
            llty = ll.FunctionType(lldouble, [lldouble, lldouble])
        elif name == "llvm.stacksave":
            llty = ll.FunctionType(llptr, [])
        elif name == "llvm.stackrestore":
            llty = ll.FunctionType(llvoid, [llptr])
        elif name == self.target.print_function:
            llty = ll.FunctionType(llvoid, [llptr], var_arg=True)
        elif name == "__artiq_personality":
            llty = ll.FunctionType(lli32, [], var_arg=True)
        elif name == "__artiq_raise":
            llty = ll.FunctionType(llvoid, [self.llty_of_type(builtins.TException())])
        elif name == "__artiq_reraise":
            llty = ll.FunctionType(llvoid, [])
        elif name == "send_rpc":
            llty = ll.FunctionType(llvoid, [lli32, llptr],
                                   var_arg=True)
        elif name == "recv_rpc":
            llty = ll.FunctionType(lli32, [llptr])
        else:
            assert False

        llfun = ll.Function(self.llmodule, llty, name)
        if name in ("__artiq_raise", "__artiq_reraise", "llvm.trap"):
            llfun.attributes.add("noreturn")
        return llfun

    def map(self, value):
        if isinstance(value, (ir.Argument, ir.Instruction, ir.BasicBlock)):
            return self.llmap[value]
        elif isinstance(value, ir.Constant):
            return self.llconst_of_const(value)
        elif isinstance(value, ir.Function):
            llfun = self.llmodule.get_global(value.name)
            if llfun is None:
                llfun = ll.Function(self.llmodule, self.llty_of_type(value.type, bare=True),
                                    value.name)
            return llfun
        else:
            assert False

    def process(self, functions):
        for func in functions:
            self.process_function(func)

        if any(functions):
            self.debug_info_emitter.finalize(functions[0].loc.source_buffer)

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

            if func.is_internal:
                self.llfunction.linkage = 'internal'

            self.llfunction.attributes.add('uwtable')

            self.llbuilder = ll.IRBuilder()
            llblock_map = {}

            disubprogram = self.debug_info_emitter.emit_subprogram(func, self.llfunction)

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

                    if insn.loc is not None:
                        diloc = self.debug_info_emitter.emit_loc(insn.loc, disubprogram)
                        llinsn.set_metadata('dbg', diloc)

                # There is no 1:1 correspondence between ARTIQ and LLVM
                # basic blocks, because sometimes we expand a single ARTIQ
                # instruction so that the result spans several LLVM basic
                # blocks. This only really matters for phis, which will
                # use a different map.
                llblock_map[block] = self.llbuilder.basic_block

            # Fourth, add incoming values to phis.
            for phi, llphi in self.phis:
                for value, block in phi.incoming():
                    llphi.add_incoming(self.map(value), llblock_map[block])
        finally:
            self.llfunction = None
            self.llmap = {}
            self.phis = []

    def process_Phi(self, insn):
        llinsn = self.llbuilder.phi(self.llty_of_type(insn.type), name=insn.name)
        self.phis.append((insn, llinsn))
        return llinsn

    def llindex(self, index):
        return ll.Constant(lli32, index)

    def process_Alloc(self, insn):
        if ir.is_environment(insn.type):
            return self.llbuilder.alloca(self.llty_of_type(insn.type, bare=True),
                                         name=insn.name)
        elif ir.is_option(insn.type):
            if len(insn.operands) == 0: # empty
                llvalue = ll.Constant(self.llty_of_type(insn.type), ll.Undefined)
                return self.llbuilder.insert_value(llvalue, ll.Constant(lli1, False), 0,
                                                   name=insn.name)
            elif len(insn.operands) == 1: # full
                llvalue = ll.Constant(self.llty_of_type(insn.type), ll.Undefined)
                llvalue = self.llbuilder.insert_value(llvalue, ll.Constant(lli1, True), 0)
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
        elif builtins.is_exception(insn.type) or types.is_constructor(insn.type):
            llalloc = self.llbuilder.alloca(self.llty_of_type(insn.type, bare=True))
            for index, operand in enumerate(insn.operands):
                lloperand = self.map(operand)
                llfieldptr = self.llbuilder.gep(llalloc, [self.llindex(0), self.llindex(index)])
                self.llbuilder.store(lloperand, llfieldptr)
            return llalloc
        elif builtins.is_allocated(insn.type):
            assert False
        else: # immutable
            llvalue = ll.Constant(self.llty_of_type(insn.type), ll.Undefined)
            for index, elt in enumerate(insn.operands):
                llvalue = self.llbuilder.insert_value(llvalue, self.map(elt), index)
            llvalue.name = insn.name
            return llvalue

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
        if isinstance(llvalue, ll.Block):
            llvalue = ll.BlockAddress(self.llfunction, llvalue)
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
        assert builtins.is_allocated(insn.object().type)
        llptr = self.llbuilder.gep(self.map(insn.object()),
                                   [self.llindex(0), self.llindex(self.attr_index(insn))],
                                   name=insn.name)
        return self.llbuilder.store(self.map(insn.value()), llptr)

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
                lllhs = self.llbuilder.sitofp(self.map(insn.lhs()), lldouble)
                llrhs = self.llbuilder.trunc(self.map(insn.rhs()), lli32)
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
        elif isinstance(lllhs.type, ll.DoubleType):
            return self.llbuilder.fcmp_ordered(op, lllhs, llrhs,
                                               name=insn.name)
        elif isinstance(lllhs.type, ll.LiteralStructType):
            # Compare aggregates (such as lists or ranges) element-by-element.
            llvalue = ll.Constant(lli1, True)
            for index in range(len(lllhs.type.elements)):
                lllhselt = self.llbuilder.extract_value(lllhs, index)
                llrhselt = self.llbuilder.extract_value(llrhs, index)
                llresult = self.llbuilder.icmp_unsigned('==', lllhselt, llrhselt)
                llvalue  = self.llbuilder.select(llresult, llvalue,
                                                 ll.Constant(lli1, False))
            return self.llbuilder.icmp_unsigned(op, llvalue, ll.Constant(lli1, True),
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
            return self.llbuilder.call(self.llbuiltin(self.target.print_function), llargs,
                                       name=insn.name)
        elif insn.op == "exncast":
            # This is an identity cast at LLVM IR level.
            return self.map(insn.operands[0])
        else:
            assert False

    def process_Closure(self, insn):
        llvalue = ll.Constant(self.llty_of_type(insn.target_function.type), ll.Undefined)
        llenv = self.llbuilder.bitcast(self.map(insn.environment()), llptr)
        llvalue = self.llbuilder.insert_value(llvalue, llenv, 0)
        llvalue = self.llbuilder.insert_value(llvalue, self.map(insn.target_function), 1,
                                              name=insn.name)
        return llvalue

    def _prepare_closure_call(self, insn):
        llclosure = self.map(insn.target_function())
        llargs    = [self.map(arg) for arg in insn.arguments()]
        llenv     = self.llbuilder.extract_value(llclosure, 0)
        llfun     = self.llbuilder.extract_value(llclosure, 1)
        return llfun, [llenv] + list(llargs)

    def _prepare_ffi_call(self, insn):
        llargs    = [self.map(arg) for arg in insn.arguments()]
        llfunty   = ll.FunctionType(self.llty_of_type(insn.type, for_return=True),
                                    [llarg.type for llarg in llargs])
        llfun     = ll.Function(self.llmodule, llfunty,
                                insn.target_function().type.name)
        return llfun, list(llargs)

    # See session.c:{send,receive}_rpc_value and comm_generic.py:_{send,receive}_rpc_value.
    def _rpc_tag(self, typ, error_handler):
        if types.is_tuple(typ):
            assert len(typ.elts) < 256
            return b"t" + bytes([len(typ.elts)]) + \
                   b"".join([self._rpc_tag(elt_type, error_handler)
                             for elt_type in typ.elts])
        elif builtins.is_none(typ):
            return b"n"
        elif builtins.is_bool(typ):
            return b"b"
        elif builtins.is_int(typ, types.TValue(32)):
            return b"i"
        elif builtins.is_int(typ, types.TValue(64)):
            return b"I"
        elif builtins.is_float(typ):
            return b"f"
        elif builtins.is_str(typ):
            return b"s"
        elif builtins.is_list(typ):
            return b"l" + self._rpc_tag(builtins.get_iterable_elt(typ),
                                        error_handler)
        elif builtins.is_range(typ):
            return b"r" + self._rpc_tag(builtins.get_iterable_elt(typ),
                                        error_handler)
        elif ir.is_option(typ):
            return b"o" + self._rpc_tag(typ.params["inner"],
                                        error_handler)
        else:
            error_handler(typ)

    def _build_rpc(self, fun_loc, fun_type, args, llnormalblock, llunwindblock):
        llservice = ll.Constant(lli32, fun_type.service)

        tag = b""

        for arg in args:
            def arg_error_handler(typ):
                printer = types.TypePrinter()
                note = diagnostic.Diagnostic("note",
                    "value of type {type}",
                    {"type": printer.name(typ)},
                    arg.loc)
                diag = diagnostic.Diagnostic("error",
                    "type {type} is not supported in remote procedure calls",
                    {"type": printer.name(arg.typ)},
                    arg.loc)
                self.engine.process(diag)
            tag += self._rpc_tag(arg.type, arg_error_handler)
        tag += b":"

        def ret_error_handler(typ):
            printer = types.TypePrinter()
            note = diagnostic.Diagnostic("note",
                "value of type {type}",
                {"type": printer.name(typ)},
                fun_loc)
            diag = diagnostic.Diagnostic("error",
                "return type {type} is not supported in remote procedure calls",
                {"type": printer.name(fun_type.ret)},
                fun_loc)
            self.engine.process(diag)
        tag += self._rpc_tag(fun_type.ret, ret_error_handler)
        tag += b"\x00"

        lltag = self.llconst_of_const(ir.Constant(tag + b"\x00", builtins.TStr()))

        llstackptr = self.llbuilder.call(self.llbuiltin("llvm.stacksave"), [])

        llargs = []
        for arg in args:
            llarg = self.map(arg)
            llargslot = self.llbuilder.alloca(llarg.type)
            self.llbuilder.store(llarg, llargslot)
            llargs.append(llargslot)

        self.llbuilder.call(self.llbuiltin("send_rpc"),
                            [llservice, lltag] + llargs)

        # Don't waste stack space on saved arguments.
        self.llbuilder.call(self.llbuiltin("llvm.stackrestore"), [llstackptr])

        # T result = {
        #   void *ptr = NULL;
        #   loop: int size = rpc_recv("tag", ptr);
        #   if(size) { ptr = alloca(size); goto loop; }
        #   else *(T*)ptr
        # }
        llprehead   = self.llbuilder.basic_block
        llhead      = self.llbuilder.append_basic_block(name=llprehead.name + ".rpc.head")
        if llunwindblock:
            llheadu = self.llbuilder.append_basic_block(name=llprehead.name + ".rpc.head.unwind")
        llalloc     = self.llbuilder.append_basic_block(name=llprehead.name + ".rpc.alloc")
        lltail      = self.llbuilder.append_basic_block(name=llprehead.name + ".rpc.tail")

        llretty = self.llty_of_type(fun_type.ret)
        llslot = self.llbuilder.alloca(llretty)
        llslotgen = self.llbuilder.bitcast(llslot, llptr)
        self.llbuilder.branch(llhead)

        self.llbuilder.position_at_end(llhead)
        llphi = self.llbuilder.phi(llslotgen.type)
        llphi.add_incoming(llslotgen, llprehead)
        if llunwindblock:
            llsize = self.llbuilder.invoke(self.llbuiltin("recv_rpc"), [llphi],
                                           llheadu, llunwindblock)
            self.llbuilder.position_at_end(llheadu)
        else:
            llsize = self.llbuilder.call(self.llbuiltin("recv_rpc"), [llphi])
        lldone = self.llbuilder.icmp_unsigned('==', llsize, ll.Constant(llsize.type, 0))
        self.llbuilder.cbranch(lldone, lltail, llalloc)

        self.llbuilder.position_at_end(llalloc)
        llalloca = self.llbuilder.alloca(lli8, llsize)
        llphi.add_incoming(llalloca, llalloc)
        self.llbuilder.branch(llhead)

        self.llbuilder.position_at_end(lltail)
        llret = self.llbuilder.load(llslot)
        if not builtins.is_allocated(fun_type.ret):
            # We didn't allocate anything except the slot for the value itself.
            # Don't waste stack space.
            self.llbuilder.call(self.llbuiltin("llvm.stackrestore"), [llstackptr])
        if llnormalblock:
            self.llbuilder.branch(llnormalblock)
        return llret

    def process_Call(self, insn):
        if types.is_rpc_function(insn.target_function().type):
            return self._build_rpc(insn.target_function().loc,
                                   insn.target_function().type,
                                   insn.arguments(),
                                   llnormalblock=None, llunwindblock=None)
        elif types.is_c_function(insn.target_function().type):
            llfun, llargs = self._prepare_ffi_call(insn)
            return self.llbuilder.call(llfun, llargs,
                                       name=insn.name)
        else:
            llfun, llargs = self._prepare_closure_call(insn)
            return self.llbuilder.call(llfun, llargs,
                                       name=insn.name)

    def process_Invoke(self, insn):
        llnormalblock = self.map(insn.normal_target())
        llunwindblock = self.map(insn.exception_target())
        if types.is_rpc_function(insn.target_function().type):
            return self._build_rpc(insn.target_function().loc,
                                   insn.target_function().type,
                                   insn.arguments(),
                                   llnormalblock, llunwindblock)
        elif types.is_c_function(insn.target_function().type):
            llfun, llargs = self._prepare_ffi_call(insn)
            return self.llbuilder.invoke(llfun, llargs, llnormalblock, llunwindblock,
                                         name=insn.name)
        else:
            llfun, llargs = self._prepare_closure_call(insn)
            return self.llbuilder.invoke(llfun, llargs, llnormalblock, llunwindblock,
                                         name=insn.name)

    def process_Select(self, insn):
        return self.llbuilder.select(self.map(insn.condition()),
                                     self.map(insn.if_true()), self.map(insn.if_false()))

    def process_Branch(self, insn):
        return self.llbuilder.branch(self.map(insn.target()))

    def process_BranchIf(self, insn):
        return self.llbuilder.cbranch(self.map(insn.condition()),
                                      self.map(insn.if_true()), self.map(insn.if_false()))

    def process_IndirectBranch(self, insn):
        llinsn = self.llbuilder.branch_indirect(self.map(insn.target()))
        for dest in insn.destinations():
            llinsn.add_destination(self.map(dest))
        return llinsn

    def process_Return(self, insn):
        if builtins.is_none(insn.value().type):
            return self.llbuilder.ret_void()
        else:
            return self.llbuilder.ret(self.map(insn.value()))

    def process_Unreachable(self, insn):
        return self.llbuilder.unreachable()

    def process_Raise(self, insn):
        llexn = self.map(insn.value())
        if insn.exception_target() is not None:
            llnormalblock = self.llfunction.append_basic_block("unreachable")
            llnormalblock.terminator = ll.Unreachable(llnormalblock)
            llnormalblock.instructions.append(llnormalblock.terminator)

            llunwindblock = self.map(insn.exception_target())
            llinsn = self.llbuilder.invoke(self.llbuiltin("__artiq_raise"), [llexn],
                                           llnormalblock, llunwindblock,
                                           name=insn.name)
        else:
            llinsn = self.llbuilder.call(self.llbuiltin("__artiq_raise"), [llexn],
                                         name=insn.name)
            self.llbuilder.unreachable()
        llinsn.attributes.add('noreturn')
        return llinsn

    def process_Reraise(self, insn):
        llinsn = self.llbuilder.call(self.llbuiltin("__artiq_reraise"), [],
                                     name=insn.name)
        llinsn.attributes.add('noreturn')
        self.llbuilder.unreachable()
        return llinsn

    def process_LandingPad(self, insn):
        # Layout on return from landing pad: {%_Unwind_Exception*, %Exception*}
        lllandingpadty = ll.LiteralStructType([llptr, llptr])
        lllandingpad = self.llbuilder.landingpad(lllandingpadty,
                                                 self.llbuiltin("__artiq_personality"),
                                                 cleanup=True)
        llrawexn = self.llbuilder.extract_value(lllandingpad, 1)
        llexn = self.llbuilder.bitcast(llrawexn, self.llty_of_type(insn.type))
        llexnnameptr = self.llbuilder.gep(llexn, [self.llindex(0), self.llindex(0)])
        llexnname = self.llbuilder.load(llexnnameptr)

        for target, typ in insn.clauses():
            if typ is None:
                llclauseexnname = ll.Constant(
                    self.llty_of_type(ir.TExceptionTypeInfo()), None)
            else:
                llclauseexnname = self.llconst_of_const(
                    ir.Constant(typ.name, ir.TExceptionTypeInfo()))
            lllandingpad.add_clause(ll.CatchClause(llclauseexnname))

            if typ is None:
                self.llbuilder.branch(self.map(target))
            else:
                llmatchingclause = self.llbuilder.icmp_unsigned('==', llexnname, llclauseexnname)
                with self.llbuilder.if_then(llmatchingclause):
                    self.llbuilder.branch(self.map(target))

        if self.llbuilder.basic_block.terminator is None:
            self.llbuilder.branch(self.map(insn.cleanup()))

        return llexn

