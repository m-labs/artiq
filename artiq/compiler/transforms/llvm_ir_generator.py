"""
:class:`LLVMIRGenerator` transforms ARTIQ intermediate representation
into LLVM intermediate representation.
"""

import os, re, types as pytypes
from collections import defaultdict
from pythonparser import ast, diagnostic
from llvmlite_artiq import ir as ll, binding as llvm
from ...language import core as language_core
from .. import types, builtins, ir


llvoid     = ll.VoidType()
lli1       = ll.IntType(1)
lli8       = ll.IntType(8)
lli32      = ll.IntType(32)
lli64      = ll.IntType(64)
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
        key = (generator,) + args
        try:
            return self.cache[key]
        except KeyError:
            result = generator(self, *args)
            self.cache[key] = result
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
    def __init__(self, engine, module_name, target, object_map, type_map):
        self.engine = engine
        self.target = target
        self.object_map = object_map
        self.type_map = type_map
        self.llcontext = target.llcontext
        self.llmodule = ll.Module(context=self.llcontext, name=module_name)
        self.llmodule.triple = target.triple
        self.llmodule.data_layout = target.data_layout
        self.llfunction = None
        self.llmap = {}
        self.llobject_map = {}
        self.phis = []
        self.debug_info_emitter = DebugInfoEmitter(self.llmodule)
        self.empty_metadata = self.llmodule.add_metadata([])

    def needs_sret(self, lltyp, may_be_large=True):
        if isinstance(lltyp, ll.VoidType):
            return False
        elif isinstance(lltyp, ll.IntType):
            return False
        elif isinstance(lltyp, ll.PointerType):
            return False
        elif may_be_large and isinstance(lltyp, ll.DoubleType):
            return False
        elif may_be_large and isinstance(lltyp, ll.LiteralStructType) \
                and len(lltyp.elements) <= 2:
            return not any([self.needs_sret(elt, may_be_large=False) for elt in lltyp.elements])
        else:
            assert isinstance(lltyp, ll.Type)
            return True

    def has_sret(self, functy):
        llretty = self.llty_of_type(functy.ret, for_return=True)
        return self.needs_sret(llretty)

    def llty_of_type(self, typ, bare=False, for_return=False):
        typ = typ.find()
        if types.is_tuple(typ):
            return ll.LiteralStructType([self.llty_of_type(eltty) for eltty in typ.elts])
        elif types.is_rpc_function(typ) or types.is_c_function(typ):
            if for_return:
                return llvoid
            else:
                return ll.LiteralStructType([])
        elif types._is_pointer(typ):
            return llptr
        elif types.is_function(typ):
            sretarg = []
            llretty = self.llty_of_type(typ.ret, for_return=True)
            if self.needs_sret(llretty):
                sretarg = [llretty.as_pointer()]
                llretty = llvoid

            envarg = llptr
            llty = ll.FunctionType(args=sretarg + [envarg] +
                                        [self.llty_of_type(typ.args[arg])
                                         for arg in typ.args] +
                                        [self.llty_of_type(ir.TOption(typ.optargs[arg]))
                                         for arg in typ.optargs],
                                   return_type=llretty)

            if bare:
                return llty
            else:
                return ll.LiteralStructType([envarg, llty.as_pointer()])
        elif types.is_method(typ):
            llfunty  = self.llty_of_type(types.get_method_function(typ))
            llselfty = self.llty_of_type(types.get_method_self(typ))
            return ll.LiteralStructType([llfunty, llselfty])
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
            llty = self.llcontext.get_identified_type("env.{}".format(typ.env_name))
            if llty.elements is None:
                llty.elements = [self.llty_of_type(typ.params[name]) for name in typ.params]

            if bare:
                return llty
            else:
                return llty.as_pointer()
        else: # Catch-all for exceptions and custom classes
            if builtins.is_exception(typ):
                name = "class.Exception" # they all share layout
            elif types.is_constructor(typ):
                name = "class.{}".format(typ.name)
            else:
                name = "instance.{}".format(typ.name)

            llty = self.llcontext.get_identified_type(name)
            if llty.elements is None:
                # First setting elements to [] will allow us to handle
                # self-referential types.
                llty.elements = []
                llty.elements = [self.llty_of_type(attrtyp)
                                 for attrtyp in typ.attributes.values()]

            if bare or not builtins.is_allocated(typ):
                return llty
            else:
                return llty.as_pointer()

    def llstr_of_str(self, value, name=None, linkage="private", unnamed_addr=True):
        if isinstance(value, str):
            assert "\0" not in value
            as_bytes = (value + "\0").encode("utf-8")
        else:
            as_bytes = value

        if name is None:
            sanitized_str = re.sub(rb"[^a-zA-Z0-9_.]", b"", as_bytes[:20]).decode('ascii')
            name = self.llmodule.get_unique_name("str.{}".format(sanitized_str))

        llstr = self.llmodule.get_global(name)
        if llstr is None:
            llstrty = ll.ArrayType(lli8, len(as_bytes))
            llstr = ll.GlobalVariable(self.llmodule, llstrty, name)
            llstr.global_constant = True
            llstr.initializer = ll.Constant(llstrty, bytearray(as_bytes))
            llstr.linkage = linkage
            llstr.unnamed_addr = unnamed_addr
        return llstr.bitcast(llptr)

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
            if ir.is_exn_typeinfo(const.type):
                # Exception typeinfo; should be merged with identical others
                name = "__artiq_exn_" + const.value
                linkage = "linkonce"
                unnamed_addr = False
            else:
                # Just a string
                name = None
                linkage = "private"
                unnamed_addr = True

            return self.llstr_of_str(const.value, name=name,
                                     linkage=linkage, unnamed_addr=unnamed_addr)
        else:
            assert False

    def llbuiltin(self, name):
        llglobal = self.llmodule.get_global(name)
        if llglobal is not None:
            return llglobal

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
        elif name == "printf":
            llty = ll.FunctionType(llvoid, [llptr], var_arg=True)
        elif name == "rtio_log":
            llty = ll.FunctionType(llvoid, [lli64, llptr], var_arg=True)
        elif name == "__artiq_personality":
            llty = ll.FunctionType(lli32, [], var_arg=True)
        elif name == "__artiq_raise":
            llty = ll.FunctionType(llvoid, [self.llty_of_type(builtins.TException())])
        elif name == "__artiq_reraise":
            llty = ll.FunctionType(llvoid, [])
        elif name == "strcmp":
            llty = ll.FunctionType(lli32, [llptr, llptr])
        elif name == "send_rpc":
            llty = ll.FunctionType(llvoid, [lli32, llptr],
                                   var_arg=True)
        elif name == "recv_rpc":
            llty = ll.FunctionType(lli32, [llptr])
        elif name == "now":
            llty = lli64
        elif name == "watchdog_set":
            llty = ll.FunctionType(lli32, [lli32])
        elif name == "watchdog_clear":
            llty = ll.FunctionType(llvoid, [lli32])
        else:
            assert False

        if isinstance(llty, ll.FunctionType):
            llglobal = ll.Function(self.llmodule, llty, name)
            if name in ("__artiq_raise", "__artiq_reraise", "llvm.trap"):
                llglobal.attributes.add("noreturn")
        else:
            llglobal = ll.GlobalVariable(self.llmodule, llty, name)

        return llglobal

    def map(self, value):
        if isinstance(value, (ir.Argument, ir.Instruction, ir.BasicBlock)):
            return self.llmap[value]
        elif isinstance(value, ir.Constant):
            return self.llconst_of_const(value)
        elif isinstance(value, ir.Function):
            llfun = self.llmodule.get_global(value.name)
            if llfun is None:
                llfunty = self.llty_of_type(value.type, bare=True)
                llfun   = ll.Function(self.llmodule, llfunty, value.name)

                llretty = self.llty_of_type(value.type.ret, for_return=True)
                if self.needs_sret(llretty):
                    llfun.args[0].add_attribute('sret')

            return llfun
        else:
            assert False

    def process(self, functions, attribute_writeback):
        for func in functions:
            self.process_function(func)

        if any(functions):
            self.debug_info_emitter.finalize(functions[0].loc.source_buffer)

        if attribute_writeback and self.object_map is not None:
            self.emit_attribute_writeback()

        return self.llmodule

    def emit_attribute_writeback(self):
        llobjects = defaultdict(lambda: [])

        for obj_id in self.object_map:
            obj_ref = self.object_map.retrieve(obj_id)
            if isinstance(obj_ref, (pytypes.FunctionType, pytypes.MethodType)):
                continue
            elif isinstance(obj_ref, type):
                _, typ = self.type_map[obj_ref]
            else:
                typ, _ = self.type_map[type(obj_ref)]

            llobject = self.llmodule.get_global("object.{}".format(obj_id))
            if llobject is not None:
                llobjects[typ].append(llobject.bitcast(llptr))

        lldatalayout = llvm.create_target_data(self.llmodule.data_layout)

        llrpcattrty = self.llcontext.get_identified_type("attr_desc")
        llrpcattrty.elements = [lli32, lli32, llptr, llptr]

        lldescty = self.llcontext.get_identified_type("type_desc")
        lldescty.elements = [llrpcattrty.as_pointer().as_pointer(), llptr.as_pointer()]

        lldescs = []
        for typ in llobjects:
            if "__objectid__" not in typ.attributes:
                continue

            if types.is_constructor(typ):
                type_name = "class.{}".format(typ.name)
            else:
                type_name = "instance.{}".format(typ.name)

            def llrpcattr_of_attr(name, typ):
                size      = self.llty_of_type(typ). \
                    get_abi_size(lldatalayout, context=self.llcontext)
                alignment = self.llty_of_type(typ). \
                    get_abi_alignment(lldatalayout, context=self.llcontext)

                def rpc_tag_error(typ):
                    print(typ)
                    assert False

                if not (types.is_function(typ) or types.is_method(typ) or
                        name == "__objectid__"):
                    rpctag   = b"Os" + self._rpc_tag(typ, error_handler=rpc_tag_error) + b":n\x00"
                    llrpctag = self.llstr_of_str(rpctag)
                else:
                    llrpctag = ll.Constant(llptr, None)

                llrpcattr = ll.GlobalVariable(self.llmodule, llrpcattrty,
                                              name="attr.{}.{}".format(type_name, name))
                llrpcattr.initializer = ll.Constant(llrpcattrty, [
                    ll.Constant(lli32, size),
                    ll.Constant(lli32, alignment),
                    llrpctag,
                    self.llstr_of_str(name)
                ])
                llrpcattr.global_constant = True
                llrpcattr.unnamed_addr = True
                llrpcattr.linkage = 'private'

                return llrpcattr

            llrpcattrs = [llrpcattr_of_attr(attr, typ.attributes[attr])
                          for attr in typ.attributes]

            llrpcattraryty = ll.ArrayType(llrpcattrty.as_pointer(), len(llrpcattrs) + 1)
            llrpcattrary = ll.GlobalVariable(self.llmodule, llrpcattraryty,
                                             name="attrs.{}".format(type_name))
            llrpcattrary.initializer = ll.Constant(llrpcattraryty,
                llrpcattrs + [ll.Constant(llrpcattrty.as_pointer(), None)])
            llrpcattrary.global_constant = True
            llrpcattrary.unnamed_addr = True
            llrpcattrary.linkage = 'private'

            llobjectaryty = ll.ArrayType(llptr, len(llobjects[typ]) + 1)
            llobjectary = ll.GlobalVariable(self.llmodule, llobjectaryty,
                                            name="objects.{}".format(type_name))
            llobjectary.initializer = ll.Constant(llobjectaryty,
                llobjects[typ] + [ll.Constant(llptr, None)])
            llobjectary.linkage = 'private'

            lldesc = ll.GlobalVariable(self.llmodule, lldescty,
                                       name="desc.{}".format(type_name))
            lldesc.initializer = ll.Constant(lldescty, [
                llrpcattrary.bitcast(llrpcattrty.as_pointer().as_pointer()),
                llobjectary.bitcast(llptr.as_pointer())
            ])
            lldesc.global_constant = True
            lldesc.linkage = 'private'
            lldescs.append(lldesc)

        llglobaldescty = ll.ArrayType(lldescty.as_pointer(), len(lldescs) + 1)
        llglobaldesc = ll.GlobalVariable(self.llmodule, llglobaldescty,
                                         name="typeinfo")
        llglobaldesc.initializer = ll.Constant(llglobaldescty,
            lldescs + [ll.Constant(lldescty.as_pointer(), None)])

    def process_function(self, func):
        try:
            self.llfunction = self.map(func)

            if func.is_internal:
                self.llfunction.linkage = 'private'

            self.llfunction.attributes.add('uwtable')

            self.llbuilder = ll.IRBuilder()
            llblock_map = {}

            disubprogram = self.debug_info_emitter.emit_subprogram(func, self.llfunction)

            # First, map arguments.
            if self.has_sret(func.type):
                llactualargs = self.llfunction.args[1:]
            else:
                llactualargs = self.llfunction.args

            for arg, llarg in zip(func.arguments, llactualargs):
                self.llmap[arg] = llarg

            # Second, create all basic blocks.
            for block in func.basic_blocks:
                llblock = self.llfunction.append_basic_block(block.name)
                self.llmap[block] = llblock

            # Third, translate all instructions.
            for block in func.basic_blocks:
                self.llbuilder.position_at_end(self.llmap[block])
                for insn in block.instructions:
                    if insn.loc is not None:
                        self.llbuilder.debug_metadata = \
                            self.debug_info_emitter.emit_loc(insn.loc, disubprogram)

                    llinsn = getattr(self, "process_" + type(insn).__name__)(insn)
                    assert llinsn is not None
                    self.llmap[insn] = llinsn

                # There is no 1:1 correspondence between ARTIQ and LLVM
                # basic blocks, because sometimes we expand a single ARTIQ
                # instruction so that the result spans several LLVM basic
                # blocks. This only really matters for phis, which are thus
                # using a different map (the following one).
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
        elif not builtins.is_allocated(insn.type):
            llvalue = ll.Constant(self.llty_of_type(insn.type), ll.Undefined)
            for index, elt in enumerate(insn.operands):
                llvalue = self.llbuilder.insert_value(llvalue, self.map(elt), index)
            llvalue.name = insn.name
            return llvalue
        else: # catchall for exceptions and custom (allocated) classes
            llalloc = self.llbuilder.alloca(self.llty_of_type(insn.type, bare=True))
            for index, operand in enumerate(insn.operands):
                lloperand = self.map(operand)
                llfieldptr = self.llbuilder.gep(llalloc, [self.llindex(0), self.llindex(index)],
                                                inbounds=True)
                self.llbuilder.store(lloperand, llfieldptr)
            return llalloc

    def llptr_to_var(self, llenv, env_ty, var_name, var_type=None):
        if var_name in env_ty.params and (var_type is None or
                env_ty.params[var_name] == var_type):
            var_index = list(env_ty.params.keys()).index(var_name)
            return self.llbuilder.gep(llenv, [self.llindex(0), self.llindex(var_index)],
                                      inbounds=True)
        else:
            outer_index = list(env_ty.params.keys()).index("$outer")
            llptr = self.llbuilder.gep(llenv, [self.llindex(0), self.llindex(outer_index)],
                                       inbounds=True)
            llouterenv = self.llbuilder.load(llptr)
            llouterenv.metadata['invariant.load'] = self.empty_metadata
            return self.llptr_to_var(llouterenv, env_ty.params["$outer"], var_name)

    def process_GetLocal(self, insn):
        env = insn.environment()
        llptr = self.llptr_to_var(self.map(env), env.type, insn.var_name)
        return self.llbuilder.load(llptr)

    def process_GetConstructor(self, insn):
        env = insn.environment()
        llptr = self.llptr_to_var(self.map(env), env.type, insn.var_name, insn.type)
        llconstr = self.llbuilder.load(llptr)
        llconstr.metadata['invariant.load'] = self.empty_metadata
        return llconstr

    def process_SetLocal(self, insn):
        env = insn.environment()
        llptr = self.llptr_to_var(self.map(env), env.type, insn.var_name)
        llvalue = self.map(insn.value())
        if isinstance(llvalue, ll.Block):
            llvalue = ll.BlockAddress(self.llfunction, llvalue)
        if llptr.type.pointee != llvalue.type:
            # The environment argument is an i8*, so that all closures can
            # unify with each other regardless of environment type or size.
            # We fixup the type on assignment into the "$outer" slot.
            assert insn.var_name == '$outer'
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
                                       inbounds=True, name=insn.name)
            return self.llbuilder.load(llptr)

    def process_SetAttr(self, insn):
        assert builtins.is_allocated(insn.object().type)
        llptr = self.llbuilder.gep(self.map(insn.object()),
                                   [self.llindex(0), self.llindex(self.attr_index(insn))],
                                   inbounds=True, name=insn.name)
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
                if "$outer" in env_ty.params:
                    outer_index = list(env_ty.params.keys()).index("$outer")
                    llptr = self.llbuilder.gep(llenv, [self.llindex(0), self.llindex(outer_index)],
                                               inbounds=True)
                    llouterenv = self.llbuilder.load(llptr)
                    llouterenv.metadata['invariant.load'] = self.empty_metadata
                    return self.llptr_to_var(llouterenv, env_ty.params["$outer"], var_name)
                else:
                    return llenv

            env, = insn.operands
            return get_outer(self.map(env), env.type)
        elif insn.op == "len":
            lst, = insn.operands
            return self.llbuilder.extract_value(self.map(lst), 0)
        elif insn.op in ("printf", "rtio_log"):
            # We only get integers, floats, pointers and strings here.
            llargs = map(self.map, insn.operands)
            return self.llbuilder.call(self.llbuiltin(insn.op), llargs,
                                       name=insn.name)
        elif insn.op == "exncast":
            # This is an identity cast at LLVM IR level.
            return self.map(insn.operands[0])
        elif insn.op == "now_mu":
            return self.llbuilder.load(self.llbuiltin("now"), name=insn.name)
        elif insn.op == "at_mu":
            time, = insn.operands
            return self.llbuilder.store(self.map(time), self.llbuiltin("now"))
        elif insn.op == "delay_mu":
            interval, = insn.operands
            llnowptr = self.llbuiltin("now")
            llnow = self.llbuilder.load(llnowptr)
            lladjusted = self.llbuilder.add(llnow, self.map(interval))
            return self.llbuilder.store(lladjusted, llnowptr)
        elif insn.op == "watchdog_set":
            interval, = insn.operands
            return self.llbuilder.call(self.llbuiltin("watchdog_set"), [self.map(interval)])
        elif insn.op == "watchdog_clear":
            id, = insn.operands
            return self.llbuilder.call(self.llbuiltin("watchdog_clear"), [self.map(id)])
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
        llargs    = [self.map(arg) for arg in insn.arguments()]
        llclosure = self.map(insn.target_function())
        llenv     = self.llbuilder.extract_value(llclosure, 0)
        if insn.static_target_function is None:
            llfun = self.llbuilder.extract_value(llclosure, 1)
        else:
            llfun = self.map(insn.static_target_function)
        return llfun, [llenv] + list(llargs)

    def _prepare_ffi_call(self, insn):
        llargs = []
        byvals = []
        for i, arg in enumerate(insn.arguments()):
            llarg = self.map(arg)
            if isinstance(llarg.type, (ll.LiteralStructType, ll.IdentifiedStructType)):
                llslot = self.llbuilder.alloca(llarg.type)
                self.llbuilder.store(llarg, llslot)
                llargs.append(llslot)
                byvals.append(i)
            else:
                llargs.append(llarg)

        llfunname = insn.target_function().type.name
        llfun     = self.llmodule.get_global(llfunname)
        if llfun is None:
            llretty = self.llty_of_type(insn.type, for_return=True)
            if self.needs_sret(llretty):
                llfunty = ll.FunctionType(llvoid, [llretty.as_pointer()] +
                                          [llarg.type for llarg in llargs])
            else:
                llfunty = ll.FunctionType(llretty, [llarg.type for llarg in llargs])

            llfun = ll.Function(self.llmodule, llfunty,
                                insn.target_function().type.name)
            if self.needs_sret(llretty):
                llfun.args[0].add_attribute('sret')
                byvals = [i + 1 for i in byvals]
            for i in byvals:
                llfun.args[i].add_attribute('byval')

        return llfun, list(llargs)

    # See session.c:{send,receive}_rpc_value and comm_generic.py:_{send,receive}_rpc_value.
    def _rpc_tag(self, typ, error_handler):
        typ = typ.find()
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
        elif '__objectid__' in typ.attributes:
            return b"O"
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
                    {"type": printer.name(arg.type)},
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

        lltag = self.llstr_of_str(tag)

        llstackptr = self.llbuilder.call(self.llbuiltin("llvm.stacksave"), [])

        llargs = []
        for arg in args:
            if builtins.is_none(arg.type):
                llargslot = self.llbuilder.alloca(ll.LiteralStructType([]))
            else:
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
        else:
            llfun, llargs = self._prepare_closure_call(insn)

        if self.has_sret(insn.target_function().type):
            llstackptr = self.llbuilder.call(self.llbuiltin("llvm.stacksave"), [])

            llresultslot = self.llbuilder.alloca(llfun.type.pointee.args[0].pointee)
            self.llbuilder.call(llfun, [llresultslot] + llargs)
            llresult = self.llbuilder.load(llresultslot)

            self.llbuilder.call(self.llbuiltin("llvm.stackrestore"), [llstackptr])

            return llresult
        else:
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

    def _quote(self, value, typ, path):
        value_id = id(value)
        if value_id in self.llobject_map:
            return self.llobject_map[value_id]

        global_name = ""
        llty = self.llty_of_type(typ)

        if types.is_constructor(typ) or types.is_instance(typ):
            llglobal = None
            llfields = []
            for attr in typ.attributes:
                if attr == "__objectid__":
                    objectid = self.object_map.store(value)
                    llfields.append(ll.Constant(lli32, objectid))

                    assert llglobal is None
                    llglobal = ll.GlobalVariable(self.llmodule, llty.pointee,
                                                 name="object.{}".format(objectid))
                    self.llobject_map[value_id] = llglobal
                else:
                    llfields.append(self._quote(getattr(value, attr), typ.attributes[attr],
                                                lambda: path() + [attr]))

            llglobal.initializer = ll.Constant(llty.pointee, llfields)
            llglobal.linkage = "private"
            return llglobal
        elif builtins.is_none(typ):
            assert value is None
            return ll.Constant.literal_struct([])
        elif builtins.is_bool(typ):
            assert value in (True, False)
            return ll.Constant(llty, value)
        elif builtins.is_int(typ):
            assert isinstance(value, (int, language_core.int))
            return ll.Constant(llty, int(value))
        elif builtins.is_float(typ):
            assert isinstance(value, float)
            return ll.Constant(llty, value)
        elif builtins.is_str(typ):
            assert isinstance(value, (str, bytes))
            return self.llstr_of_str(value)
        elif builtins.is_list(typ):
            assert isinstance(value, list)
            elt_type  = builtins.get_iterable_elt(typ)
            llelts    = [self._quote(value[i], elt_type, lambda: path() + [str(i)])
                         for i in range(len(value))]
            lleltsary = ll.Constant(ll.ArrayType(self.llty_of_type(elt_type), len(llelts)),
                                    llelts)

            llglobal  = ll.GlobalVariable(self.llmodule, lleltsary.type,
                                          self.llmodule.scope.deduplicate("quoted.list"))
            llglobal.initializer = lleltsary
            llglobal.linkage = "private"

            lleltsptr = llglobal.bitcast(lleltsary.type.element.as_pointer())
            llconst   = ll.Constant(llty, [ll.Constant(lli32, len(llelts)), lleltsptr])
            return llconst
        elif types.is_function(typ):
            # RPC and C functions have no runtime representation; ARTIQ
            # functions are initialized explicitly.
            return ll.Constant(llty, ll.Undefined)
        else:
            print(typ)
            assert False

    def process_Quote(self, insn):
        assert self.object_map is not None
        return self._quote(insn.value, insn.type, lambda: [repr(insn.value)])

    def process_Select(self, insn):
        return self.llbuilder.select(self.map(insn.condition()),
                                     self.map(insn.if_true()), self.map(insn.if_false()))

    def process_Branch(self, insn):
        return self.llbuilder.branch(self.map(insn.target()))

    process_Delay = process_Branch

    def process_BranchIf(self, insn):
        return self.llbuilder.cbranch(self.map(insn.condition()),
                                      self.map(insn.if_true()), self.map(insn.if_false()))

    process_Loop = process_BranchIf

    def process_IndirectBranch(self, insn):
        llinsn = self.llbuilder.branch_indirect(self.map(insn.target()))
        for dest in insn.destinations():
            llinsn.add_destination(self.map(dest))
        return llinsn

    def process_Return(self, insn):
        if builtins.is_none(insn.value().type):
            return self.llbuilder.ret_void()
        else:
            llvalue = self.map(insn.value())
            if self.needs_sret(llvalue.type):
                self.llbuilder.store(llvalue, self.llfunction.args[0])
                return self.llbuilder.ret_void()
            else:
                return self.llbuilder.ret(llvalue)

    def process_Unreachable(self, insn):
        return self.llbuilder.unreachable()

    def _gen_raise(self, insn, func, args):
        if insn.exception_target() is not None:
            llnormalblock = self.llfunction.append_basic_block("unreachable")
            llnormalblock.terminator = ll.Unreachable(llnormalblock)
            llnormalblock.instructions.append(llnormalblock.terminator)

            llunwindblock = self.map(insn.exception_target())
            llinsn = self.llbuilder.invoke(func, args,
                                           llnormalblock, llunwindblock,
                                           name=insn.name)
        else:
            llinsn = self.llbuilder.call(func, args,
                                         name=insn.name)
            self.llbuilder.unreachable()
        llinsn.attributes.add('noreturn')
        return llinsn

    def process_Raise(self, insn):
        llexn = self.map(insn.value())
        return self._gen_raise(insn, self.llbuiltin("__artiq_raise"), [llexn])

    def process_Reraise(self, insn):
        return self._gen_raise(insn, self.llbuiltin("__artiq_reraise"), [])

    def process_LandingPad(self, insn):
        # Layout on return from landing pad: {%_Unwind_Exception*, %Exception*}
        lllandingpadty = ll.LiteralStructType([llptr, llptr])
        lllandingpad = self.llbuilder.landingpad(lllandingpadty,
                                                 self.llbuiltin("__artiq_personality"),
                                                 cleanup=True)
        llrawexn = self.llbuilder.extract_value(lllandingpad, 1)
        llexn = self.llbuilder.bitcast(llrawexn, self.llty_of_type(insn.type))
        llexnnameptr = self.llbuilder.gep(llexn, [self.llindex(0), self.llindex(0)],
                                          inbounds=True)
        llexnname = self.llbuilder.load(llexnnameptr)

        for target, typ in insn.clauses():
            if typ is None:
                llclauseexnname = ll.Constant(
                    self.llty_of_type(ir.TExceptionTypeInfo()), None)
            else:
                llclauseexnname = self.llconst_of_const(
                    ir.Constant("{}:{}".format(typ.id, typ.name),
                                ir.TExceptionTypeInfo()))
            lllandingpad.add_clause(ll.CatchClause(llclauseexnname))

            if typ is None:
                self.llbuilder.branch(self.map(target))
            else:
                llexnmatch = self.llbuilder.call(self.llbuiltin("strcmp"),
                                                 [llexnname, llclauseexnname])
                llmatchingclause = self.llbuilder.icmp_unsigned('==',
                                                                llexnmatch, ll.Constant(lli32, 0))
                with self.llbuilder.if_then(llmatchingclause):
                    self.llbuilder.branch(self.map(target))

        if self.llbuilder.basic_block.terminator is None:
            self.llbuilder.branch(self.map(insn.cleanup()))

        return llexn
