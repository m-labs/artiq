"""
:class:`LLVMIRGenerator` transforms ARTIQ intermediate representation
into LLVM intermediate representation.
"""

import os, re, types as pytypes, numpy
from collections import defaultdict
from pythonparser import ast, diagnostic
from llvmlite import ir as ll, binding as llvm
from ...language import core as language_core
from .. import types, builtins, ir
from ..embedding import SpecializedFunction
from artiq.compiler.targets import RV32GTarget


llvoid     = ll.VoidType()
llunit     = ll.LiteralStructType([])
lli1       = ll.IntType(1)
lli8       = ll.IntType(8)
lli32      = ll.IntType(32)
lli64      = ll.IntType(64)
lldouble   = ll.DoubleType()
llptr      = ll.IntType(8).as_pointer()
llptrptr   = ll.IntType(8).as_pointer().as_pointer()
llslice    = ll.LiteralStructType([llptr, lli32])
llsliceptr = ll.LiteralStructType([llptr, lli32]).as_pointer()
llmetadata = ll.MetaDataType()


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
        self.llcompileunit = None
        self.cache = {}

        llident = self.llmodule.add_named_metadata('llvm.ident')
        llident.add(self.emit_metadata(["ARTIQ"]))

        llflags = self.llmodule.add_named_metadata('llvm.module.flags')
        llflags.add(self.emit_metadata([2, "Debug Info Version", 3]))
        llflags.add(self.emit_metadata([2, "Dwarf Version", 4]))

    def emit_metadata(self, operands):
        def map_operand(operand):
            if operand is None:
                return ll.Constant(llmetadata, None)
            elif isinstance(operand, str):
                return ll.MetaDataString(self.llmodule, operand)
            elif isinstance(operand, int):
                return ll.Constant(lli32, operand)
            elif isinstance(operand, (list, tuple)):
                return self.emit_metadata(operand)
            else:
                assert isinstance(operand, ll.NamedValue)
                return operand
        return self.llmodule.add_metadata(list(map(map_operand, operands)))

    def emit_debug_info(self, kind, operands, is_distinct=False):
        return self.llmodule.add_debug_info(kind, operands, is_distinct)

    @memoize
    def emit_file(self, source_buffer):
        source_dir, source_file = os.path.split(source_buffer.name)
        return self.emit_debug_info("DIFile", {
            "filename":        source_file,
            "directory":       source_dir,
        })

    @memoize
    def emit_compile_unit(self, source_buffer):
        return self.emit_debug_info("DICompileUnit", {
            "language":        ll.DIToken("DW_LANG_Python"),
            "file":            self.emit_file(source_buffer),
            "producer":        "ARTIQ",
            "runtimeVersion":  0,
            "emissionKind":    2,   # full=1, lines only=2
        }, is_distinct=True)

    @memoize
    def emit_subroutine_type(self, typ):
        return self.emit_debug_info("DISubroutineType", {
            "types":           self.emit_metadata([None])
        })

    @memoize
    def emit_subprogram(self, func, llfunc):
        source_buffer = func.loc.source_buffer

        if self.llcompileunit is None:
            self.llcompileunit = self.emit_compile_unit(source_buffer)
            llcompileunits = self.llmodule.add_named_metadata('llvm.dbg.cu')
            llcompileunits.add(self.llcompileunit)

        display_name = "{}{}".format(func.name, types.TypePrinter().name(func.type))
        return self.emit_debug_info("DISubprogram", {
            "name":            func.name,
            "linkageName":     llfunc.name,
            "type":            self.emit_subroutine_type(func.type),
            "file":            self.emit_file(source_buffer),
            "line":            func.loc.line(),
            "unit":            self.llcompileunit,
            "scope":           self.emit_file(source_buffer),
            "scopeLine":       func.loc.line(),
            "isLocal":         func.is_internal,
            "isDefinition":    True,
            "retainedNodes":   self.emit_metadata([])
        }, is_distinct=True)

    @memoize
    def emit_loc(self, loc, scope):
        return self.emit_debug_info("DILocation", {
            "line":            loc.line(),
            "column":          loc.column(),
            "scope":           scope
        })


class ABILayoutInfo:
    """Caches DataLayout size/alignment lookup results.

    llvmlite's Type.get_abi_{size, alignment}() are implemented in a very
    inefficient way, in particular _get_ll_pointer_type() used to construct the
    corresponding llvm::Type is. We thus cache the results, optionally directly
    using the compiler type as a key.

    (This is a separate class for use with @memoize.)
    """

    def __init__(self, lldatalayout, llcontext, llty_of_type):
        self.cache = {}
        self.lldatalayout = lldatalayout
        self.llcontext = llcontext
        self.llty_of_type = llty_of_type

    @memoize
    def get_size_align(self, llty):
        lowered = llty._get_ll_pointer_type(self.lldatalayout, self.llcontext)
        return (self.lldatalayout.get_pointee_abi_size(lowered),
                self.lldatalayout.get_pointee_abi_alignment(lowered))

    @memoize
    def get_size_align_for_type(self, typ):
        return self.get_size_align(self.llty_of_type(typ))


class LLVMIRGenerator:
    def __init__(self, engine, module_name, target, embedding_map):
        self.engine = engine
        self.target = target
        self.embedding_map = embedding_map
        self.llcontext = target.llcontext
        self.llmodule = ll.Module(context=self.llcontext, name=module_name)
        self.llmodule.triple = target.triple
        self.llmodule.data_layout = target.data_layout
        self.lldatalayout = llvm.create_target_data(self.llmodule.data_layout)
        self.abi_layout_info = ABILayoutInfo(self.lldatalayout, self.llcontext,
            self.llty_of_type)
        self.function_flags = None
        self.llfunction = None
        self.llmap = {}
        self.llobject_map = {}
        self.llpred_map = {}
        self.phis = []
        self.debug_info_emitter = DebugInfoEmitter(self.llmodule)
        self.empty_metadata = self.llmodule.add_metadata([])
        self.quote_fail_msg = None

        # Maximum alignment required according to the target platform ABI. As this is
        # not directly exposed by LLVM, just take the maximum across all the "big"
        # elementary types we use. (Vector types, should we ever support them, are
        # likely contenders for even larger alignment requirements.)
        self.max_target_alignment = max(map(
            lambda t: self.abi_layout_info.get_size_align(t)[1],
            [lli64, lldouble, llptr]
        ))

    def add_pred(self, pred, block):
        if block not in self.llpred_map:
            self.llpred_map[block] = set()
        self.llpred_map[block].add(pred)

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
        elif types.is_rpc(typ) or types.is_external_function(typ) or types.is_subkernel(typ):
            if for_return:
                return llvoid
            else:
                return llunit
        elif types._is_pointer(typ):
            return ll.PointerType(self.llty_of_type(typ["elt"]))
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
                return llunit
        elif builtins.is_bool(typ):
            return lli1
        elif builtins.is_int(typ):
            return ll.IntType(builtins.get_int_width(typ))
        elif builtins.is_float(typ):
            return lldouble
        elif builtins.is_array(typ):
            llshapety = self.llty_of_type(typ.attributes["shape"])
            llbufferty = self.llty_of_type(typ.attributes["buffer"])
            return ll.LiteralStructType([llbufferty, llshapety])
        elif builtins.is_listish(typ):
            lleltty = self.llty_of_type(builtins.get_iterable_elt(typ))
            lltyp = ll.LiteralStructType([lleltty.as_pointer(), lli32])
            if builtins.is_list(typ):
                lltyp = lltyp.as_pointer()
            return lltyp
        elif builtins.is_range(typ):
            lleltty = self.llty_of_type(builtins.get_iterable_elt(typ))
            return ll.LiteralStructType([lleltty, lleltty, lleltty])
        elif ir.is_basic_block(typ):
            return llptr
        elif ir.is_option(typ):
            return ll.LiteralStructType([lli1, self.llty_of_type(typ.params["value"])])
        elif ir.is_keyword(typ):
            return ll.LiteralStructType([llslice, self.llty_of_type(typ.params["value"])])
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
                name = "C.Exception" # they all share layout
            elif types.is_constructor(typ):
                name = "C.{}".format(typ.name)
            else:
                name = "I.{}".format(typ.name)

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
            as_bytes = value.encode("utf-8")
        else:
            as_bytes = value

        if name is None:
            sanitized_str = re.sub(rb"[^a-zA-Z0-9_.]", b"", as_bytes[:20]).decode('ascii')
            name = self.llmodule.get_unique_name("S.{}".format(sanitized_str))

        llstr = self.llmodule.globals.get(name)
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
            if isinstance(llty, ll.PointerType):
                return ll.Constant(llty, None)
            else:
                return ll.Constant(llty, [])
        elif const.value is True:
            return ll.Constant(llty, True)
        elif const.value is False:
            return ll.Constant(llty, False)
        elif isinstance(const.value, (int, float)):
            return ll.Constant(llty, const.value)
        elif isinstance(const.value, (str, bytes)):
            if isinstance(const.value, str):
                value = const.value.encode('utf-8')
            else:
                value = const.value

            llptr = self.llstr_of_str(value, linkage="private", unnamed_addr=True)
            lllen = ll.Constant(lli32, len(value))
            return ll.Constant(llty, (llptr, lllen))
        else:
            assert False

    def llbuiltin(self, name):
        llglobal = self.llmodule.globals.get(name)
        if llglobal is not None:
            return llglobal

        if name in "llvm.donothing":
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
        elif name == "__py_modsi3":
            llty = ll.FunctionType(lli32, [lli32, lli32])
        elif name == "__py_moddi3":
            llty = ll.FunctionType(lli64, [lli64, lli64])
        elif name == "__py_moddf3":
            llty = ll.FunctionType(lldouble, [lldouble, lldouble])
        elif name == self.target.print_function:
            llty = ll.FunctionType(llvoid, [llptr], var_arg=True)
        elif name == "rtio_log":
            llty = ll.FunctionType(llvoid, [llptr], var_arg=True)
        elif name == "__artiq_personality":
            llty = ll.FunctionType(lli32, [], var_arg=True)
        elif name == "__artiq_raise":
            llty = ll.FunctionType(llvoid, [self.llty_of_type(builtins.TException())])
        elif name == "__artiq_resume":
            llty = ll.FunctionType(llvoid, [])
        elif name == "__artiq_end_catch":
            llty = ll.FunctionType(llvoid, [])
        elif name == "memcmp":
            llty = ll.FunctionType(lli32, [llptr, llptr, lli32])
        elif name == "rpc_send":
            llty = ll.FunctionType(llvoid, [lli32, llsliceptr, llptrptr])
        elif name == "rpc_send_async":
            llty = ll.FunctionType(llvoid, [lli32, llsliceptr, llptrptr])
        elif name == "rpc_recv":
            llty = ll.FunctionType(lli32, [llptr])

        elif name == "subkernel_send_message":
            llty = ll.FunctionType(llvoid, [lli32, lli1, lli8, lli8, llsliceptr, llptrptr])
        elif name == "subkernel_load_run":
            llty = ll.FunctionType(llvoid, [lli32, lli8, lli1])
        elif name == "subkernel_await_finish":
            llty = ll.FunctionType(llvoid, [lli32, lli64])
        elif name == "subkernel_await_message":
            llty = ll.FunctionType(lli8, [lli32, lli64, llsliceptr, lli8, lli8])

        # with now-pinning
        elif name == "now":
            llty = lli64

        # without now-pinning
        elif name == "now_mu":
            llty = ll.FunctionType(lli64, [])
        elif name == "at_mu":
            llty = ll.FunctionType(llvoid, [lli64])
        elif name == "delay_mu":
            llty = ll.FunctionType(llvoid, [lli64])

        else:
            assert False

        if isinstance(llty, ll.FunctionType):
            llglobal = ll.Function(self.llmodule, llty, name)
            if name in ("__artiq_raise", "__artiq_resume", "llvm.trap"):
                llglobal.attributes.add("noreturn")
            if name in ("rtio_log", "rpc_send", "rpc_send_async",
                        self.target.print_function):
                llglobal.attributes.add("nounwind")
            if name.find("__py_") == 0:
                llglobal.linkage = 'linkonce_odr'
                self.emit_intrinsic(name, llglobal)
        else:
            llglobal = ll.GlobalVariable(self.llmodule, llty, name)

        return llglobal

    def emit_intrinsic(self, name, llfun):
        llbuilder = ll.IRBuilder()
        llbuilder.position_at_end(llfun.append_basic_block("entry"))

        if name == "__py_modsi3" or name == "__py_moddi3":
            if name == "__py_modsi3":
                llty = lli32
            elif name == "__py_moddi3":
                llty = lli64
            else:
                assert False

            """
            Reference Objects/intobject.c
                xdivy = x / y;
                xmody = (long)(x - (unsigned long)xdivy * y);
                /* If the signs of x and y differ, and the remainder is non-0,
                 * C89 doesn't define whether xdivy is now the floor or the
                 * ceiling of the infinitely precise quotient.  We want the floor,
                 * and we have it iff the remainder's sign matches y's.
                 */
                if (xmody && ((y ^ xmody) < 0) /* i.e. and signs differ */) {
                    xmody += y;
                    // ...
                }
            """
            llx, lly = llfun.args
            llxdivy = llbuilder.sdiv(llx, lly)
            llxremy = llbuilder.srem(llx, lly)

            llxmodynonzero = llbuilder.icmp_signed('!=', llxremy, ll.Constant(llty, 0))
            lldiffsign = llbuilder.icmp_signed('<', llbuilder.xor(llx, lly), ll.Constant(llty, 0))

            llcond = llbuilder.and_(llxmodynonzero, lldiffsign)
            with llbuilder.if_then(llcond):
                llbuilder.ret(llbuilder.add(llxremy, lly))
            llbuilder.ret(llxremy)
        elif name == "__py_moddf3":
            """
            Reference Objects/floatobject.c
                mod = fmod(vx, wx);
                /* fmod is typically exact, so vx-mod is *mathematically* an
                   exact multiple of wx.  But this is fp arithmetic, and fp
                   vx - mod is an approximation; the result is that div may
                   not be an exact integral value after the division, although
                   it will always be very close to one.
                */
                // ...
                if (mod) {
                    /* ensure the remainder has the same sign as the denominator */
                    if ((wx < 0) != (mod < 0)) {
                        mod += wx;
                        // ...
                    }
                }
                else {
                    /* the remainder is zero, and in the presence of signed zeroes
                       fmod returns different results across platforms; ensure
                       it has the same sign as the denominator; we'd like to do
                       "mod = wx * 0.0", but that may get optimized away */
                    mod *= mod;  /* hide "mod = +0" from optimizer */
                    if (wx < 0.0)
                        mod = -mod;
                }
            """
            llv, llw = llfun.args
            llrem = llbuilder.frem(llv, llw)

            llremnonzero = llbuilder.fcmp_unordered('!=', llrem, ll.Constant(lldouble, 0.0))
            llwltzero = llbuilder.fcmp_ordered('<', llw, ll.Constant(lldouble, 0.0))
            llremltzero = llbuilder.fcmp_ordered('<', llrem, ll.Constant(lldouble, 0.0))
            lldiffsign = llbuilder.icmp_unsigned('!=', llwltzero, llremltzero)

            llcond = llbuilder.and_(llremnonzero, lldiffsign)
            with llbuilder.if_then(llcond):
                llbuilder.ret(llbuilder.fadd(llrem, llw))
            llbuilder.ret(llrem)
        else:
            assert False

    def get_function(self, typ, name):
        llfun = self.llmodule.globals.get(name)
        if llfun is None:
            llfunty = self.llty_of_type(typ, bare=True)
            llfun   = ll.Function(self.llmodule, llfunty, name)

            llretty = self.llty_of_type(typ.find().ret, for_return=True)
            if self.needs_sret(llretty):
                llfun.args[0].add_attribute('sret')
        return llfun

    def get_function_with_undef_env(self, typ, name):
        llfun     = self.get_function(typ, name)
        llclosure = ll.Constant(self.llty_of_type(typ), [
                        ll.Constant(llptr, ll.Undefined),
                        llfun
                    ])
        return llclosure

    def map(self, value):
        if isinstance(value, (ir.Argument, ir.Instruction, ir.BasicBlock)):
            return self.llmap[value]
        elif isinstance(value, ir.Constant):
            return self.llconst_of_const(value)
        elif isinstance(value, ir.Function):
            return self.get_function(value.type, value.name)
        else:
            assert False

    def process(self, functions, attribute_writeback):
        for func in functions:
            self.process_function(func)

        if attribute_writeback and self.embedding_map is not None:
            self.emit_attribute_writeback()

        return self.llmodule

    def emit_attribute_writeback(self):
        llobjects = defaultdict(lambda: [])

        for obj_id, obj_ref, obj_typ in self.embedding_map.iter_objects():
            llobject = self.llmodule.globals.get("O.{}".format(obj_id))
            if llobject is not None:
                llobjects[obj_typ].append(llobject.bitcast(llptr))

        llrpcattrty = self.llcontext.get_identified_type("A")
        llrpcattrty.elements = [lli32, llslice, llslice]

        lldescty = self.llcontext.get_identified_type("D")
        lldescty.elements = [llrpcattrty.as_pointer().as_pointer(), llptr.as_pointer()]

        lldescs = []
        for typ in llobjects:
            if "__objectid__" not in typ.attributes:
                continue

            if types.is_constructor(typ):
                type_name = "C.{}".format(typ.name)
            else:
                type_name = "I.{}".format(typ.name)

            def llrpcattr_of_attr(offset, name, typ):
                def rpc_tag_error(typ):
                    print(typ)
                    assert False

                if name == "__objectid__":
                    rpctag = b""
                else:
                    rpctag = b"Os" + ir.rpc_tag(typ, error_handler=rpc_tag_error) + b":n"

                llrpcattrinit = ll.Constant(llrpcattrty, [
                    ll.Constant(lli32, offset),
                    self.llconst_of_const(ir.Constant(rpctag, builtins.TStr())),
                    self.llconst_of_const(ir.Constant(name, builtins.TStr()))
                ])

                if name == "__objectid__":
                    return self.get_or_define_global(name, llrpcattrty, llrpcattrinit)

                llrpcattr = ll.GlobalVariable(self.llmodule, llrpcattrty,
                                              name="A.{}.{}".format(type_name, name))
                llrpcattr.initializer = llrpcattrinit
                llrpcattr.global_constant = True
                llrpcattr.unnamed_addr = True
                llrpcattr.linkage = 'private'

                return llrpcattr

            offset = 0
            llrpcattrs = []
            for attr in typ.attributes:
                attrtyp = typ.attributes[attr]
                size, alignment = self.abi_layout_info.get_size_align_for_type(attrtyp)

                if offset % alignment != 0:
                    offset += alignment - (offset % alignment)

                if types.is_instance(typ) and attr not in typ.constant_attributes:
                    try:
                        llrpcattrs.append(llrpcattr_of_attr(offset, attr, attrtyp))
                    except ValueError:
                        pass

                offset += size

            if len(llrpcattrs) == 1:
                # Don't bother serializing objects that only have __objectid__
                # since there's nothing to writeback anyway.
                continue

            llrpcattraryty = ll.ArrayType(llrpcattrty.as_pointer(), len(llrpcattrs) + 1)
            llrpcattrary = ll.GlobalVariable(self.llmodule, llrpcattraryty,
                                             name="Ax.{}".format(type_name))
            llrpcattrary.initializer = ll.Constant(llrpcattraryty,
                llrpcattrs + [ll.Constant(llrpcattrty.as_pointer(), None)])
            llrpcattrary.global_constant = True
            llrpcattrary.unnamed_addr = True
            llrpcattrary.linkage = 'private'

            llobjectaryty = ll.ArrayType(llptr, len(llobjects[typ]) + 1)
            llobjectary = ll.GlobalVariable(self.llmodule, llobjectaryty,
                                            name="Ox.{}".format(type_name))
            llobjectary.initializer = ll.Constant(llobjectaryty,
                llobjects[typ] + [ll.Constant(llptr, None)])
            llobjectary.linkage = 'private'

            lldesc = ll.GlobalVariable(self.llmodule, lldescty,
                                       name="D.{}".format(type_name))
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
            self.function_flags = func.flags
            self.llfunction = self.map(func)

            if func.is_internal:
                self.llfunction.linkage = 'private'
            if func.is_cold:
                self.llfunction.attributes.add('cold')
                self.llfunction.attributes.add('noinline')
            if 'inline' in func.flags:
                self.llfunction.attributes.add('inlinehint')
            if 'forceinline' in func.flags:
                self.llfunction.attributes.add('alwaysinline')

            self.llfunction.attributes.add('uwtable')
            self.llfunction.attributes.personality = self.llbuiltin("__artiq_personality")

            self.llbuilder = ll.IRBuilder()
            llblock_map = {}

            # this is the predecessor map, from basic block to the set of its
            # predecessors
            # handling for branch and cbranch is here, and the handling of
            # indirectbr and landingpad are in their respective process_*
            # function
            self.llpred_map = llpred_map = {}
            branch_fn = self.llbuilder.branch
            cbranch_fn = self.llbuilder.cbranch
            def override_branch(block):
                nonlocal self, branch_fn
                self.add_pred(self.llbuilder.basic_block, block)
                return branch_fn(block)

            def override_cbranch(pred, bbif, bbelse):
                nonlocal self, cbranch_fn
                self.add_pred(self.llbuilder.basic_block, bbif)
                self.add_pred(self.llbuilder.basic_block, bbelse)
                return cbranch_fn(pred, bbif, bbelse)

            self.llbuilder.branch = override_branch
            self.llbuilder.cbranch = override_cbranch

            if not func.is_generated:
                lldisubprogram = self.debug_info_emitter.emit_subprogram(func, self.llfunction)
                self.llfunction.set_metadata('dbg', lldisubprogram)

            # First, map arguments.
            if self.has_sret(func.type):
                llactualargs = self.llfunction.args[1:]
            else:
                llactualargs = self.llfunction.args

            for arg, llarg in zip(func.arguments, llactualargs):
                llarg.name = arg.name
                self.llmap[arg] = llarg

            # Second, create all basic blocks.
            for block in func.basic_blocks:
                llblock = self.llfunction.append_basic_block(block.name)
                self.llmap[block] = llblock

            # Third, translate all instructions.
            for block in func.basic_blocks:
                self.llbuilder.position_at_end(self.llmap[block])
                old_block = None
                if len(block.instructions) == 1 and \
                    isinstance(block.instructions[0], ir.LandingPad):
                    old_block = self.llbuilder.basic_block
                for insn in block.instructions:
                    if insn.loc is not None and not func.is_generated:
                        self.llbuilder.debug_metadata = \
                            self.debug_info_emitter.emit_loc(insn.loc, lldisubprogram)

                    llinsn = getattr(self, "process_" + type(insn).__name__)(insn)
                    assert llinsn is not None
                    self.llmap[insn] = llinsn

                # There is no 1:1 correspondence between ARTIQ and LLVM
                # basic blocks, because sometimes we expand a single ARTIQ
                # instruction so that the result spans several LLVM basic
                # blocks. This only really matters for phis, which are thus
                # using a different map (the following one).
                if old_block is None:
                    llblock_map[block] = self.llbuilder.basic_block
                else:
                    llblock_map[block] = old_block

            # Fourth, add incoming values to phis.
            for phi, llphi in self.phis:
                for value, block in phi.incoming():
                    if isinstance(phi.type, builtins.TException):
                        # a hack to patch phi from landingpad
                        # because landingpad is a single bb in artiq IR, but
                        # generates multiple bb, we need to find out the
                        # predecessor to figure out the actual bb
                        landingpad = llblock_map[block]
                        for pred in llpred_map[llphi.parent]:
                            if pred in llpred_map and landingpad in llpred_map[pred]:
                                llphi.add_incoming(self.map(value), pred)
                                break
                        else:
                            llphi.add_incoming(self.map(value), landingpad)
                    else:
                        llphi.add_incoming(self.map(value), llblock_map[block])
        finally:
            self.function_flags = None
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
        elif types._is_pointer(insn.type) or (builtins.is_listish(insn.type)
                                              and not builtins.is_array(insn.type)):
            llsize = self.map(insn.operands[0])
            lleltty = self.llty_of_type(builtins.get_iterable_elt(insn.type))
            llalloc = self.llbuilder.alloca(lleltty, size=llsize)
            if types._is_pointer(insn.type):
                return llalloc
            if builtins.is_list(insn.type):
                llvalue = self.llbuilder.alloca(self.llty_of_type(insn.type).pointee, size=1)
                self.llbuilder.store(llalloc, self.llbuilder.gep(llvalue,
                                                                 [self.llindex(0),
                                                                  self.llindex(0)],
                                                                 inbounds=True))
                self.llbuilder.store(llsize, self.llbuilder.gep(llvalue,
                                                                 [self.llindex(0),
                                                                  self.llindex(1)],
                                                                 inbounds=True))
            else:
                llvalue = ll.Constant(self.llty_of_type(insn.type), ll.Undefined)
                llvalue = self.llbuilder.insert_value(llvalue, llalloc, 0)
                llvalue = self.llbuilder.insert_value(llvalue, llsize, 1)
            return llvalue
        elif (not builtins.is_allocated(insn.type) or ir.is_keyword(insn.type)
              or builtins.is_array(insn.type)):
            llvalue = ll.Constant(self.llty_of_type(insn.type), ll.Undefined)
            for index, elt in enumerate(insn.operands):
                llvalue = self.llbuilder.insert_value(llvalue, self.map(elt), index)
            llvalue.name = insn.name
            return llvalue
        elif types.is_constructor(insn.type):
            return self.get_class(insn.type)
        else: # catchall for exceptions and custom (allocated) classes
            llalloc = self.llbuilder.alloca(self.llty_of_type(insn.type, bare=True))
            for index, operand in enumerate(insn.operands):
                lloperand = self.map(operand)
                llfieldptr = self.llbuilder.gep(llalloc, [self.llindex(0), self.llindex(index)],
                                                inbounds=True)
                self.llbuilder.store(lloperand, llfieldptr)
            return llalloc

    def llptr_to_var(self, llenv, env_ty, var_name):
        if var_name in env_ty.params:
            var_index = list(env_ty.params.keys()).index(var_name)
            return self.llbuilder.gep(llenv, [self.llindex(0), self.llindex(var_index)],
                                      inbounds=True)
        else:
            outer_index = list(env_ty.params.keys()).index("$outer")
            llptr = self.llbuilder.gep(llenv, [self.llindex(0), self.llindex(outer_index)],
                                       inbounds=True)
            llouterenv = self.llbuilder.load(llptr)
            llouterenv.set_metadata('invariant.load', self.empty_metadata)
            llouterenv.set_metadata('nonnull', self.empty_metadata)
            return self.llptr_to_var(llouterenv, env_ty.params["$outer"], var_name)

    def mark_dereferenceable(self, load):
        assert isinstance(load, ll.LoadInstr) and isinstance(load.type, ll.PointerType)
        pointee_size, _ = self.abi_layout_info.get_size_align(load.type.pointee)
        metadata = self.llmodule.add_metadata([ll.Constant(lli64, pointee_size)])
        load.set_metadata('dereferenceable', metadata)

    def process_GetLocal(self, insn):
        env = insn.environment()
        llptr = self.llptr_to_var(self.map(env), env.type, insn.var_name)
        llptr.name = "ptr.{}.{}".format(env.name, insn.var_name)
        llvalue = self.llbuilder.load(llptr, name="val.{}.{}".format(env.name, insn.var_name))
        if isinstance(llvalue.type, ll.PointerType):
            self.mark_dereferenceable(llvalue)
        return llvalue

    def process_SetLocal(self, insn):
        env = insn.environment()
        llvalue = self.map(insn.value())
        if isinstance(llvalue.type, ll.VoidType):
            # We store NoneType as {} but return it as void. So, bail out here.
            return ll.Constant(ll.LiteralStructType([]), [])
        llptr = self.llptr_to_var(self.map(env), env.type, insn.var_name)
        llptr.name = "ptr.{}.{}".format(env.name, insn.var_name)
        if isinstance(llvalue, ll.Block):
            llvalue = ll.BlockAddress(self.llfunction, llvalue)
        if llptr.type.pointee != llvalue.type:
            # The environment argument is an i8*, so that all closures can
            # unify with each other regardless of environment type or size.
            # We fixup the type on assignment into the "$outer" slot.
            assert insn.var_name == '$outer'
            llvalue = self.llbuilder.bitcast(llvalue, llptr.type.pointee)
        return self.llbuilder.store(llvalue, llptr)

    def process_GetArgFromRemote(self, insn):
        llstackptr = self.llbuilder.call(self.llbuiltin("llvm.stacksave"), [],
                                         name="subkernel.arg.stack")
        llval = self._build_rpc_recv(insn.arg_type, llstackptr)
        return llval

    def process_GetOptArgFromRemote(self, insn):
        # optarg = index < rcv_count ? Some(rcv_recv()) : None
        llhead = self.llbuilder.basic_block
        llrcv = self.llbuilder.append_basic_block(name="optarg.get.{}".format(insn.arg_name))
        
        # argument received
        self.llbuilder.position_at_end(llrcv)
        llstackptr = self.llbuilder.call(self.llbuiltin("llvm.stacksave"), [],
                                         name="subkernel.arg.stack")
        llval = self._build_rpc_recv(insn.arg_type, llstackptr)
        llrpcretblock = self.llbuilder.basic_block  # 'return' from rpc_recv, will be needed later
        
        # create the tail block, needs to be after the rpc recv tail block
        lltail = self.llbuilder.append_basic_block(name="optarg.tail.{}".format(insn.arg_name))
        self.llbuilder.branch(lltail)

        # go back to head to add a branch to the tail
        self.llbuilder.position_at_end(llhead)
        llargrcvd = self.llbuilder.icmp_unsigned("<", self.map(insn.index), self.map(insn.rcv_count))
        self.llbuilder.cbranch(llargrcvd, llrcv, lltail)

        # argument not received/after arg recvd
        self.llbuilder.position_at_end(lltail)

        llargtype = self.llty_of_type(insn.arg_type)

        llphi_arg_present = self.llbuilder.phi(lli1, name="optarg.phi.present.{}".format(insn.arg_name))
        llphi_arg = self.llbuilder.phi(llargtype, name="optarg.phi.{}".format(insn.arg_name))

        llphi_arg_present.add_incoming(ll.Constant(lli1, 0), llhead)
        llphi_arg.add_incoming(ll.Constant(llargtype, ll.Undefined), llhead)

        llphi_arg_present.add_incoming(ll.Constant(lli1, 1), llrpcretblock)
        llphi_arg.add_incoming(llval, llrpcretblock)
        
        lloptarg = ll.Constant(ll.LiteralStructType([lli1, llargtype]), ll.Undefined)
        lloptarg = self.llbuilder.insert_value(lloptarg, llphi_arg_present, 0)
        lloptarg = self.llbuilder.insert_value(lloptarg, llphi_arg, 1)

        return lloptarg

    def attr_index(self, typ, attr):
        return list(typ.attributes.keys()).index(attr)

    def get_or_define_global(self, name, llty, llvalue=None):
        if llvalue is None:
            llvalue = ll.Constant(llty, ll.Undefined)

        if name in self.llmodule.globals:
            llglobal = self.llmodule.get_global(name)
        else:
            llglobal = ll.GlobalVariable(self.llmodule, llty, name)
            llglobal.linkage = "private"
            if llvalue is not None:
                llglobal.initializer = llvalue
        return llglobal

    def get_class(self, typ):
        assert types.is_constructor(typ)
        llty = self.llty_of_type(typ).pointee
        return self.get_or_define_global("C.{}".format(typ.name), llty)

    def get_global_closure_ptr(self, typ, attr):
        closure_type = typ.attributes[attr]
        assert types.is_constructor(typ)
        assert types.is_function(closure_type) or types.is_rpc(closure_type) or types.is_subkernel(closure_type)
        if types.is_external_function(closure_type) or types.is_rpc(closure_type) or types.is_subkernel(closure_type):
            return None

        llty = self.llty_of_type(typ.attributes[attr])
        return self.get_or_define_global("F.{}.{}".format(typ.name, attr), llty)

    def get_global_closure(self, typ, attr):
        llclosureptr = self.get_global_closure_ptr(typ, attr)
        if llclosureptr is None:
            return None

        # LLVM's GlobalOpt pass only considers for SROA the globals that
        # are used only by GEPs, so we have to do this stupid hack.
        llenvptr = self.llbuilder.gep(llclosureptr, [self.llindex(0), self.llindex(0)])
        llfunptr = self.llbuilder.gep(llclosureptr, [self.llindex(0), self.llindex(1)])
        return [llenvptr, llfunptr]

    def load_closure(self, typ, attr):
        llclosureparts = self.get_global_closure(typ, attr)
        if llclosureparts is None:
            return ll.Constant(llunit, [])

        # See above.
        llenvptr, llfunptr = llclosureparts
        llenv = self.llbuilder.load(llenvptr)
        llfun = self.llbuilder.load(llfunptr)
        llclosure = ll.Constant(ll.LiteralStructType([llenv.type, llfun.type]), ll.Undefined)
        llclosure = self.llbuilder.insert_value(llclosure, llenv, 0)
        llclosure = self.llbuilder.insert_value(llclosure, llfun, 1)
        return llclosure

    def store_closure(self, llclosure, typ, attr):
        llclosureparts = self.get_global_closure(typ, attr)
        assert llclosureparts is not None

        llenvptr, llfunptr = llclosureparts
        llenv = self.llbuilder.extract_value(llclosure, 0)
        llfun = self.llbuilder.extract_value(llclosure, 1)
        self.llbuilder.store(llenv, llenvptr)
        return self.llbuilder.store(llfun, llfunptr)

    def process_GetAttr(self, insn):
        typ, attr = insn.object().type, insn.attr
        if types.is_tuple(typ):
            return self.llbuilder.extract_value(self.map(insn.object()), attr,
                                                name=insn.name)
        elif builtins.is_array(typ) or not builtins.is_allocated(typ):
            return self.llbuilder.extract_value(self.map(insn.object()),
                                                self.attr_index(typ, attr),
                                                name=insn.name)
        else:
            if attr in typ.attributes:
                index = self.attr_index(typ, attr)
                obj = self.map(insn.object())
            elif attr in typ.constructor.attributes:
                index = self.attr_index(typ.constructor, attr)
                obj = self.get_class(typ.constructor)
            else:
                assert False

            if types.is_method(insn.type) and attr not in typ.attributes:
                llfun = self.load_closure(typ.constructor, attr)
                llfun.name = "met.{}.{}".format(typ.constructor.name, attr)
                llself = self.map(insn.object())

                llmethodty = self.llty_of_type(insn.type)
                llmethod = ll.Constant(llmethodty, ll.Undefined)
                llmethod = self.llbuilder.insert_value(llmethod, llfun,
                                                       self.attr_index(insn.type, '__func__'))
                llmethod = self.llbuilder.insert_value(llmethod, llself,
                                                       self.attr_index(insn.type, '__self__'))
                return llmethod
            elif types.is_function(insn.type) and attr in typ.attributes and \
                    types.is_constructor(typ):
                llfun = self.load_closure(typ, attr)
                llfun.name = "fun.{}".format(insn.name)
                return llfun
            else:
                llptr = self.llbuilder.gep(obj, [self.llindex(0), self.llindex(index)],
                                           inbounds=True, name="ptr.{}".format(insn.name))
                llvalue = self.llbuilder.load(llptr, name="val.{}".format(insn.name))
                if types.is_instance(typ) and attr in typ.constant_attributes:
                    llvalue.set_metadata('invariant.load', self.empty_metadata)
                if isinstance(llvalue.type, ll.PointerType):
                    self.mark_dereferenceable(llvalue)
                return llvalue

    def process_SetAttr(self, insn):
        typ, attr = insn.object().type, insn.attr
        assert builtins.is_allocated(typ)

        if attr in typ.attributes:
            obj = self.map(insn.object())
        elif attr in typ.constructor.attributes:
            typ = typ.constructor
            obj = self.get_class(typ)
        else:
            assert False

        llvalue = self.map(insn.value())
        if types.is_function(insn.value().type) and attr in typ.attributes and \
                types.is_constructor(typ):
            return self.store_closure(llvalue, typ, attr)
        else:
            llptr = self.llbuilder.gep(obj, [self.llindex(0),
                                             self.llindex(self.attr_index(typ, attr))],
                                       inbounds=True, name=insn.name)
            return self.llbuilder.store(llvalue, llptr)

    def process_Offset(self, insn):
        base, idx = insn.base(), insn.index()
        llelts, llidx = map(self.map, (base, idx))
        if builtins.is_listish(base.type):
            # This is list-ish.
            if builtins.is_list(base.type):
                llelts = self.llbuilder.load(self.llbuilder.gep(llelts,
                                                                [self.llindex(0),
                                                                 self.llindex(0)],
                                                                inbounds=True))
            else:
                llelts = self.llbuilder.extract_value(llelts, 0)
        llelt = self.llbuilder.gep(llelts, [llidx], inbounds=True)
        return llelt

    def process_GetElem(self, insn):
        llelt = self.process_Offset(insn)
        llvalue = self.llbuilder.load(llelt)
        if isinstance(llvalue.type, ll.PointerType):
            self.mark_dereferenceable(llvalue)
        return llvalue

    def process_SetElem(self, insn):
        base, idx = insn.base(), insn.index()
        llelts, llidx = map(self.map, (base, idx))
        if builtins.is_listish(base.type):
            # This is list-ish.
            if builtins.is_list(base.type):
                llelts = self.llbuilder.load(self.llbuilder.gep(llelts,
                                                                [self.llindex(0),
                                                                 self.llindex(0)],
                                                                inbounds=True))
            else:
                llelts = self.llbuilder.extract_value(llelts, 0)
        llelt = self.llbuilder.gep(llelts, [llidx], inbounds=True)
        return self.llbuilder.store(self.map(insn.value()), llelt)

    def process_Coerce(self, insn):
        typ, value_typ = insn.type, insn.value().type
        if typ == value_typ:
            return self.map(insn.value())
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

    def add_fast_math_flags(self, llvalue):
        if 'fast-math' in self.function_flags:
            llvalue.opname = llvalue.opname + ' fast'

    def process_Arith(self, insn):
        if isinstance(insn.op, ast.Add):
            if builtins.is_float(insn.type):
                llvalue = self.llbuilder.fadd(self.map(insn.lhs()), self.map(insn.rhs()),
                                              name=insn.name)
                self.add_fast_math_flags(llvalue)
                return llvalue
            else:
                return self.llbuilder.add(self.map(insn.lhs()), self.map(insn.rhs()),
                                          name=insn.name)
        elif isinstance(insn.op, ast.Sub):
            if builtins.is_float(insn.type):
                llvalue = self.llbuilder.fsub(self.map(insn.lhs()), self.map(insn.rhs()),
                                              name=insn.name)
                self.add_fast_math_flags(llvalue)
                return llvalue
            else:
                return self.llbuilder.sub(self.map(insn.lhs()), self.map(insn.rhs()),
                                          name=insn.name)
        elif isinstance(insn.op, ast.Mult):
            if builtins.is_float(insn.type):
                llvalue = self.llbuilder.fmul(self.map(insn.lhs()), self.map(insn.rhs()),
                                              name=insn.name)
                self.add_fast_math_flags(llvalue)
                return llvalue
            else:
                return self.llbuilder.mul(self.map(insn.lhs()), self.map(insn.rhs()),
                                          name=insn.name)
        elif isinstance(insn.op, ast.Div):
            if builtins.is_float(insn.lhs().type):
                llvalue = self.llbuilder.fdiv(self.map(insn.lhs()), self.map(insn.rhs()),
                                              name=insn.name)
                self.add_fast_math_flags(llvalue)
                return llvalue
            else:
                lllhs = self.llbuilder.sitofp(self.map(insn.lhs()), self.llty_of_type(insn.type))
                llrhs = self.llbuilder.sitofp(self.map(insn.rhs()), self.llty_of_type(insn.type))
                llvalue = self.llbuilder.fdiv(lllhs, llrhs,
                                              name=insn.name)
                self.add_fast_math_flags(llvalue)
                return llvalue
        elif isinstance(insn.op, ast.FloorDiv):
            if builtins.is_float(insn.type):
                llvalue = self.llbuilder.fdiv(self.map(insn.lhs()), self.map(insn.rhs()))
                self.add_fast_math_flags(llvalue)
                return self.llbuilder.call(self.llbuiltin("llvm.floor.f64"), [llvalue],
                                           name=insn.name)
            else:
                return self.llbuilder.sdiv(self.map(insn.lhs()), self.map(insn.rhs()),
                                           name=insn.name)
        elif isinstance(insn.op, ast.Mod):
            lllhs, llrhs = map(self.map, (insn.lhs(), insn.rhs()))
            if builtins.is_float(insn.type):
                intrinsic = "__py_moddf3"
            elif builtins.is_int32(insn.type):
                intrinsic = "__py_modsi3"
            elif builtins.is_int64(insn.type):
                intrinsic = "__py_moddi3"
            return self.llbuilder.call(self.llbuiltin(intrinsic), [lllhs, llrhs],
                                       name=insn.name)
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

        if isinstance(lllhs.type, ll.PointerType) and \
                isinstance(lllhs.type.pointee, ll.LiteralStructType):
            lllhs = self.llbuilder.load(lllhs)
            llrhs = self.llbuilder.load(llrhs)

        if isinstance(lllhs.type, ll.IntType):
            return self.llbuilder.icmp_signed(op, lllhs, llrhs,
                                                name=insn.name)
        elif isinstance(lllhs.type, ll.PointerType):
            return self.llbuilder.icmp_unsigned(op, lllhs, llrhs,
                                                name=insn.name)
        elif isinstance(lllhs.type, ll.DoubleType):
            llresult = self.llbuilder.fcmp_ordered(op, lllhs, llrhs,
                                                   name=insn.name)
            self.add_fast_math_flags(llresult)
            return llresult
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
            llhas_arg = self.llbuilder.extract_value(lloptarg, 0, name="opt.has")
            llarg = self.llbuilder.extract_value(lloptarg, 1, name="opt.val")
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
                    llouterenv.set_metadata('invariant.load', self.empty_metadata)
                    llouterenv.set_metadata('nonnull', self.empty_metadata)
                    return self.llptr_to_var(llouterenv, env_ty.params["$outer"], var_name)
                else:
                    return llenv

            env, = insn.operands
            return get_outer(self.map(env), env.type)
        elif insn.op == "len":
            collection, = insn.operands
            if builtins.is_array(collection.type):
                # Return length of outermost dimension.
                shape = self.llbuilder.extract_value(self.map(collection),
                    self.attr_index(collection.type, "shape"))
                return self.llbuilder.extract_value(shape, 0)
            elif builtins.is_list(collection.type):
                return self.llbuilder.load(self.llbuilder.gep(self.map(collection),
                                                              [self.llindex(0),
                                                               self.llindex(1)]))
            else:
                return self.llbuilder.extract_value(self.map(collection), 1)
        elif insn.op in ("printf", "rtio_log"):
            # We only get integers, floats, pointers and strings here.
            lloperands = []
            for i, operand in enumerate(insn.operands):
                lloperand = self.map(operand)
                if i == 0 and (insn.op == "printf" or insn.op == "rtio_log"):
                    lloperands.append(self.llbuilder.extract_value(lloperand, 0))
                elif builtins.is_str(operand.type) or builtins.is_bytes(operand.type):
                    lloperands.append(self.llbuilder.extract_value(lloperand, 1))
                    lloperands.append(self.llbuilder.extract_value(lloperand, 0))
                else:
                    lloperands.append(lloperand)
            func_name = self.target.print_function if insn.op == "printf" else insn.op
            return self.llbuilder.call(self.llbuiltin(func_name), lloperands,
                                       name=insn.name)
        elif insn.op == "exncast":
            # This is an identity cast at LLVM IR level.
            return self.map(insn.operands[0])
        elif insn.op == "now_mu":
            if self.target.now_pinning:
                # Word swap now.old as CPU is little endian
                # Most significant word is stored in lower address (see generated csr.rs)
                csr_offset = 2 if isinstance(self.target, RV32GTarget) else 1

                llnow_hiptr = self.llbuilder.bitcast(self.llbuiltin("now"), lli32.as_pointer())
                llnow_loptr = self.llbuilder.gep(llnow_hiptr, [self.llindex(csr_offset)])
                llnow_hi = self.llbuilder.load(llnow_hiptr, name="now.hi")
                llnow_lo = self.llbuilder.load(llnow_loptr, name="now.lo")
                llzext_hi = self.llbuilder.zext(llnow_hi, lli64)
                llshifted_hi = self.llbuilder.shl(llzext_hi, ll.Constant(lli64, 32))
                llzext_lo = self.llbuilder.zext(llnow_lo, lli64)
                return self.llbuilder.or_(llshifted_hi, llzext_lo)
            else:
                return self.llbuilder.call(self.llbuiltin("now_mu"), [])
        elif insn.op == "at_mu":
            time, = insn.operands
            lltime = self.map(time)
            if self.target.now_pinning:
                csr_offset = 2 if isinstance(self.target, RV32GTarget) else 1

                lltime_hi = self.llbuilder.trunc(self.llbuilder.lshr(lltime, ll.Constant(lli64, 32)), lli32)
                lltime_lo = self.llbuilder.trunc(lltime, lli32)
                llnow_hiptr = self.llbuilder.bitcast(self.llbuiltin("now"), lli32.as_pointer())
                llnow_loptr = self.llbuilder.gep(llnow_hiptr, [self.llindex(csr_offset)])
                llstore_hi = self.llbuilder.store_atomic(lltime_hi, llnow_hiptr, ordering="seq_cst", align=4)
                llstore_lo = self.llbuilder.store_atomic(lltime_lo, llnow_loptr, ordering="seq_cst", align=4)
                return llstore_lo
            else:
                return self.llbuilder.call(self.llbuiltin("at_mu"), [lltime])
        elif insn.op == "delay_mu":
            interval, = insn.operands
            llinterval = self.map(interval)
            if self.target.now_pinning:
                # Word swap now.old as CPU is little endian
                # Most significant word is stored in lower address (see generated csr.rs)
                csr_offset = 2 if isinstance(self.target, RV32GTarget) else 1

                llnow_hiptr = self.llbuilder.bitcast(self.llbuiltin("now"), lli32.as_pointer())
                llnow_loptr = self.llbuilder.gep(llnow_hiptr, [self.llindex(csr_offset)])
                llnow_hi = self.llbuilder.load(llnow_hiptr, name="now.hi")
                llnow_lo = self.llbuilder.load(llnow_loptr, name="now.lo")
                llzext_hi = self.llbuilder.zext(llnow_hi, lli64)
                llshifted_hi = self.llbuilder.shl(llzext_hi, ll.Constant(lli64, 32))
                llzext_lo = self.llbuilder.zext(llnow_lo, lli64)
                llnow = self.llbuilder.or_(llshifted_hi, llzext_lo)

                lladjusted = self.llbuilder.add(llnow, llinterval, name="now.new")
                lladjusted_hi = self.llbuilder.trunc(self.llbuilder.lshr(lladjusted, ll.Constant(lli64, 32)), lli32)
                lladjusted_lo = self.llbuilder.trunc(lladjusted, lli32)
                llstore_hi = self.llbuilder.store_atomic(lladjusted_hi, llnow_hiptr, ordering="seq_cst", align=4)
                llstore_lo = self.llbuilder.store_atomic(lladjusted_lo, llnow_loptr, ordering="seq_cst", align=4)
                return llstore_lo
            else:
                return self.llbuilder.call(self.llbuiltin("delay_mu"), [llinterval])
        elif insn.op == "end_catch":
            return self.llbuilder.call(self.llbuiltin("__artiq_end_catch"), [])
        elif insn.op == "subkernel_await_finish":
            llsid = self.map(insn.operands[0])
            lltimeout = self.map(insn.operands[1])
            return self.llbuilder.call(self.llbuiltin("subkernel_await_finish"), [llsid, lltimeout],
                                       name="subkernel.await.finish")
        elif insn.op == "subkernel_retrieve_return":
            llsid = self.map(insn.operands[0])
            lltimeout = self.map(insn.operands[1])
            lltagptr = self._build_subkernel_tags([insn.type])
            self.llbuilder.call(self.llbuiltin("subkernel_await_message"), 
                                [llsid, lltimeout, lltagptr, ll.Constant(lli8, 1), ll.Constant(lli8, 1)],
                                name="subkernel.await.message")
            llstackptr = self.llbuilder.call(self.llbuiltin("llvm.stacksave"), [],
                                             name="subkernel.arg.stack")
            return self._build_rpc_recv(insn.type, llstackptr)
        elif insn.op == "subkernel_preload":
            llsid = self.map(insn.operands[0])
            lldest = ll.Constant(lli8, insn.operands[1].value)
            return self.llbuilder.call(self.llbuiltin("subkernel_load_run"), [llsid, lldest, ll.Constant(lli1, 0)], 
                                name="subkernel.preload")
        elif insn.op == "subkernel_send":
            llmsgid = self.map(insn.operands[0])
            lldest = self.map(insn.operands[1])
            return self._build_subkernel_message(llmsgid, lldest, [insn.operands[2]])
        elif insn.op == "subkernel_recv":
            llmsgid = self.map(insn.operands[0])
            lltimeout = self.map(insn.operands[1])
            lltagptr = self._build_subkernel_tags([insn.type])
            self.llbuilder.call(self.llbuiltin("subkernel_await_message"), 
                                [llmsgid, lltimeout, lltagptr, ll.Constant(lli8, 1), ll.Constant(lli8, 1)],
                                name="subkernel.await.message")
            llstackptr = self.llbuilder.call(self.llbuiltin("llvm.stacksave"), [],
                                             name="subkernel.arg.stack")
            return self._build_rpc_recv(insn.type, llstackptr)
        else:
            assert False

    def process_BuiltinInvoke(self, insn):
        llnormalblock = self.map(insn.normal_target())
        llunwindblock = self.map(insn.exception_target())
        if insn.op == "subkernel_retrieve_return":
            llsid = self.map(insn.operands[0])
            lltimeout = self.map(insn.operands[1])
            lltagptr = self._build_subkernel_tags([insn.type])
            llheadu = self.llbuilder.append_basic_block(name="subkernel.await.unwind")
            self.llbuilder.invoke(self.llbuiltin("subkernel_await_message"), 
                                  [llsid, lltimeout, lltagptr, ll.Constant(lli8, 1), ll.Constant(lli8, 1)],
                                  llheadu, llunwindblock,
                                  name="subkernel.await.message")
            self.llbuilder.position_at_end(llheadu)
            llstackptr = self.llbuilder.call(self.llbuiltin("llvm.stacksave"), [],
                                             name="subkernel.arg.stack")
            return self._build_rpc_recv(insn.type, llstackptr, llnormalblock, llunwindblock)
        elif insn.op == "subkernel_await_finish":
            llsid = self.map(insn.operands[0])
            lltimeout = self.map(insn.operands[1])
            return self.llbuilder.invoke(self.llbuiltin("subkernel_await_finish"), [llsid, lltimeout],
                                         llnormalblock, llunwindblock,
                                         name="subkernel.await.finish")
        elif insn.op == "subkernel_recv":
            llmsgid = self.map(insn.operands[0])
            lltimeout = self.map(insn.operands[1])
            lltagptr = self._build_subkernel_tags([insn.type])
            llheadu = self.llbuilder.append_basic_block(name="subkernel.await.unwind")
            self.llbuilder.invoke(self.llbuiltin("subkernel_await_message"), 
                                  [llmsgid, lltimeout, lltagptr, ll.Constant(lli8, 1), ll.Constant(lli8, 1)],
                                  llheadu, llunwindblock,
                                  name="subkernel.await.message")
            self.llbuilder.position_at_end(llheadu)
            llstackptr = self.llbuilder.call(self.llbuiltin("llvm.stacksave"), [],
                                             name="subkernel.arg.stack")
            return self._build_rpc_recv(insn.type, llstackptr, llnormalblock, llunwindblock)
        else:
            assert False

    def process_SubkernelAwaitArgs(self, insn):
        llmin = self.map(insn.operands[0])
        llmax = self.map(insn.operands[1])
        lltagptr = self._build_subkernel_tags(insn.arg_types)
        return self.llbuilder.call(self.llbuiltin("subkernel_await_message"), 
                                    [ll.Constant(lli32, -1), ll.Constant(lli64, 10_000), lltagptr, llmin, llmax],
                                    name="subkernel.await.args")

    def process_Closure(self, insn):
        llenv = self.map(insn.environment())
        llenv = self.llbuilder.bitcast(llenv, llptr)
        llfun = self.map(insn.target_function)
        llvalue = ll.Constant(self.llty_of_type(insn.target_function.type), ll.Undefined)
        llvalue = self.llbuilder.insert_value(llvalue, llenv, 0)
        llvalue = self.llbuilder.insert_value(llvalue, llfun, 1, name=insn.name)
        return llvalue

    def _prepare_closure_call(self, insn):
        llargs    = [self.map(arg) for arg in insn.arguments()]
        llclosure = self.map(insn.target_function())
        if insn.static_target_function is None:
            if isinstance(llclosure, ll.Constant):
                name = "fun.{}".format(llclosure.constant[1].name)
            else:
                name = "fun.{}".format(llclosure.name)
            llfun = self.llbuilder.extract_value(llclosure, 1, name=name)
        else:
            llfun = self.map(insn.static_target_function)
        llenv     = self.llbuilder.extract_value(llclosure, 0, name="env.fun")
        return llfun, [llenv] + list(llargs), {}, None

    def _prepare_ffi_call(self, insn):
        llargs = []
        llarg_attrs = {}

        stack_save_needed = False
        for i, arg in enumerate(insn.arguments()):
            llarg = self.map(arg)            
            if isinstance(llarg.type, (ll.LiteralStructType, ll.IdentifiedStructType)):
                stack_save_needed = True
                break

        if stack_save_needed:
            llcallstackptr = self.llbuilder.call(self.llbuiltin("llvm.stacksave"), [])
        else:
            llcallstackptr = None

        for i, arg in enumerate(insn.arguments()):
            llarg = self.map(arg)
            if isinstance(llarg.type, (ll.LiteralStructType, ll.IdentifiedStructType)):
                llslot = self.llbuilder.alloca(llarg.type)
                self.llbuilder.store(llarg, llslot)
                llargs.append(llslot)
                llarg_attrs[i] = "byval"
            else:
                llargs.append(llarg)

        llretty = self.llty_of_type(insn.type, for_return=True)
        is_sret = self.needs_sret(llretty)
        if is_sret:
            llarg_attrs = {i + 1: a for (i, a) in llarg_attrs.items()}
            llarg_attrs[0] = "sret"

        llfunname = insn.target_function().type.name
        llfun     = self.llmodule.globals.get(llfunname)
        if llfun is None:
            # Function has not been declared in the current LLVM module, do it now.
            if is_sret:
                llfunty = ll.FunctionType(llvoid, [llretty.as_pointer()] +
                                          [llarg.type for llarg in llargs])
            else:
                llfunty = ll.FunctionType(llretty, [llarg.type for llarg in llargs])

            llfun = ll.Function(self.llmodule, llfunty,
                                insn.target_function().type.name)
            for idx, attr in llarg_attrs.items():
                llfun.args[idx].add_attribute(attr)
            if 'nounwind' in insn.target_function().type.flags:
                llfun.attributes.add('nounwind')
            if 'nowrite' in insn.target_function().type.flags and not is_sret:
                # Even if "nowrite" is correct from the user's perspective (doesn't
                # access any other memory observable to ARTIQ Python), this isn't
                # true on the LLVM IR level for sret return values.
                llfun.attributes.add('inaccessiblememonly')

        return llfun, list(llargs), llarg_attrs, llcallstackptr

    def _build_subkernel_tags(self, tag_list):
        def ret_error_handler(typ):
            printer = types.TypePrinter()
            note = diagnostic.Diagnostic("note",
                "value of type {type}",
                {"type": printer.name(typ)},
                fun_loc)
            diag = diagnostic.Diagnostic("error",
                "type {type} is not supported in subkernels",
                {"type": printer.name(fun_type.ret)},
                fun_loc, notes=[note])
            self.engine.process(diag)
        tag = b"".join([ir.rpc_tag(arg_type, ret_error_handler) for arg_type in tag_list])
        lltag = self.llconst_of_const(ir.Constant(tag, builtins.TStr()))
        lltagptr = self.llbuilder.alloca(lltag.type)
        self.llbuilder.store(lltag, lltagptr)
        return lltagptr

    def _build_rpc_recv(self, ret, llstackptr, llnormalblock=None, llunwindblock=None):
        # T result = {
        #   void *ret_ptr = alloca(sizeof(T));
        #   void *ptr = ret_ptr;
        #   loop: int size = rpc_recv(ptr);
        #   // Non-zero: Provide `size` bytes of extra storage for variable-length data.
        #   if(size) { ptr = alloca(size); goto loop; }
        #   else *(T*)ret_ptr
        # }
        llprehead   = self.llbuilder.basic_block
        llhead      = self.llbuilder.append_basic_block(name="rpc.head")
        if llunwindblock:
            llheadu = self.llbuilder.append_basic_block(name="rpc.head.unwind")
        llalloc     = self.llbuilder.append_basic_block(name="rpc.continue")
        lltail      = self.llbuilder.append_basic_block(name="rpc.tail")

        llretty = self.llty_of_type(ret)
        llslot = self.llbuilder.alloca(llretty, name="rpc.ret.alloc")
        llslotgen = self.llbuilder.bitcast(llslot, llptr, name="rpc.ret.ptr")
        self.llbuilder.branch(llhead)

        self.llbuilder.position_at_end(llhead)
        llphi = self.llbuilder.phi(llslotgen.type, name="rpc.ptr")
        llphi.add_incoming(llslotgen, llprehead)
        if llunwindblock:
            llsize = self.llbuilder.invoke(self.llbuiltin("rpc_recv"), [llphi],
                                           llheadu, llunwindblock,
                                           name="rpc.size.next")
            self.llbuilder.position_at_end(llheadu)
        else:
            llsize = self.llbuilder.call(self.llbuiltin("rpc_recv"), [llphi],
                                         name="rpc.size.next")
        lldone = self.llbuilder.icmp_unsigned('==', llsize, ll.Constant(llsize.type, 0),
                                              name="rpc.done")
        self.llbuilder.cbranch(lldone, lltail, llalloc)

        self.llbuilder.position_at_end(llalloc)
        llalloca = self.llbuilder.alloca(lli8, llsize, name="rpc.alloc")
        llalloca.align = self.max_target_alignment
        llphi.add_incoming(llalloca, llalloc)
        self.llbuilder.branch(llhead)

        self.llbuilder.position_at_end(lltail)
        llret = self.llbuilder.load(llslot, name="rpc.ret")
        if not ret.fold(False, lambda r, t: r or builtins.is_allocated(t)):
            # We didn't allocate anything except the slot for the value itself.
            # Don't waste stack space.
            self.llbuilder.call(self.llbuiltin("llvm.stackrestore"), [llstackptr])
        if llnormalblock:
            self.llbuilder.branch(llnormalblock)
        return llret

    def _build_arg_tag(self, args, call_type):
        tag = b""
        for arg in args:
            def arg_error_handler(typ):
                printer = types.TypePrinter()
                note = diagnostic.Diagnostic("note",
                    "value of type {type}",
                    {"type": printer.name(typ)},
                    arg.loc)
                diag = diagnostic.Diagnostic("error",
                    "type {type} is not supported in {call_type} calls",
                    {"type": printer.name(arg.type), "call_type": call_type},
                    arg.loc, notes=[note])
                self.engine.process(diag)
            tag += ir.rpc_tag(arg.type, arg_error_handler)
        tag += b":"
        return tag

    def _build_rpc(self, fun_loc, fun_type, args, llnormalblock, llunwindblock):
        llservice = ll.Constant(lli32, fun_type.service)

        tag = self._build_arg_tag(args, call_type="remote procedure")

        def ret_error_handler(typ):
            printer = types.TypePrinter()
            note = diagnostic.Diagnostic("note",
                "value of type {type}",
                {"type": printer.name(typ)},
                fun_loc)
            diag = diagnostic.Diagnostic("error",
                "return type {type} is not supported in remote procedure calls",
                {"type": printer.name(fun_type.ret)},
                fun_loc, notes=[note])
            self.engine.process(diag)
        tag += ir.rpc_tag(fun_type.ret, ret_error_handler)

        llstackptr = self.llbuilder.call(self.llbuiltin("llvm.stacksave"), [],
                                         name="rpc.stack")

        lltag = self.llconst_of_const(ir.Constant(tag, builtins.TStr()))
        lltagptr = self.llbuilder.alloca(lltag.type)
        self.llbuilder.store(lltag, lltagptr)

        llargs = self.llbuilder.alloca(llptr, ll.Constant(lli32, len(args)),
                                       name="rpc.args")
        for index, arg in enumerate(args):
            if builtins.is_none(arg.type):
                llargslot = self.llbuilder.alloca(llunit,
                                                  name="rpc.arg{}".format(index))
            else:
                llarg = self.map(arg)
                llargslot = self.llbuilder.alloca(llarg.type,
                                                  name="rpc.arg{}".format(index))
                self.llbuilder.store(llarg, llargslot)
            llargslot = self.llbuilder.bitcast(llargslot, llptr)

            llargptr = self.llbuilder.gep(llargs, [ll.Constant(lli32, index)])
            self.llbuilder.store(llargslot, llargptr)

        if fun_type.is_async:
            self.llbuilder.call(self.llbuiltin("rpc_send_async"),
                                [llservice, lltagptr, llargs])
        else:
            self.llbuilder.call(self.llbuiltin("rpc_send"),
                                [llservice, lltagptr, llargs])

        # Don't waste stack space on saved arguments.
        self.llbuilder.call(self.llbuiltin("llvm.stackrestore"), [llstackptr])

        if fun_type.is_async:
            # If this RPC is called using an `invoke` ARTIQ IR instruction, there will be
            # no other instructions in this basic block. Since this RPC is async, it cannot
            # possibly raise an exception, so add an explicit jump to the normal successor.
            if llunwindblock:
                self.llbuilder.branch(llnormalblock)

            return ll.Undefined

        llret = self._build_rpc_recv(fun_type.ret, llstackptr, llnormalblock, llunwindblock)

        return llret

    def _build_subkernel_call(self, fun_loc, fun_type, args):
        llsid = ll.Constant(lli32, fun_type.sid)
        lldest = ll.Constant(lli8, fun_type.destination)
        # run the kernel first
        self.llbuilder.call(self.llbuiltin("subkernel_load_run"), [llsid, lldest, ll.Constant(lli1, 1)])

        if args:
            # only send args if there's anything to send, 'self' is excluded
            self._build_subkernel_message(llsid, lldest, args)

        return llsid

    def _build_subkernel_message(self, llid, lldest, args):
        # args (or messages) are sent in the same vein as RPC
        tag = self._build_arg_tag(args, call_type="subkernel")

        llstackptr = self.llbuilder.call(self.llbuiltin("llvm.stacksave"), [],
                                            name="subkernel.stack")
        lltag = self.llconst_of_const(ir.Constant(tag, builtins.TStr()))
        lltagptr = self.llbuilder.alloca(lltag.type)
        self.llbuilder.store(lltag, lltagptr)

        llargs = self.llbuilder.alloca(llptr, ll.Constant(lli32, len(args)),
                                    name="subkernel.args")
        for index, arg in enumerate(args):
            if builtins.is_none(arg.type):
                llargslot = self.llbuilder.alloca(llunit,
                                                name="subkernel.arg{}".format(index))
            else:
                llarg = self.map(arg)
                llargslot = self.llbuilder.alloca(llarg.type,
                                                name="subkernel.arg{}".format(index))
                self.llbuilder.store(llarg, llargslot)
            llargslot = self.llbuilder.bitcast(llargslot, llptr)

            llargptr = self.llbuilder.gep(llargs, [ll.Constant(lli32, index)])
            self.llbuilder.store(llargslot, llargptr)

        llargcount = ll.Constant(lli8, len(args))

        llisreturn = ll.Constant(lli1, False)
        self.llbuilder.call(self.llbuiltin("subkernel_send_message"),
                            [llid, llisreturn, lldest, llargcount, lltagptr, llargs])
        return self.llbuilder.call(self.llbuiltin("llvm.stackrestore"), [llstackptr])

    def _build_subkernel_return(self, insn):
        # builds a remote return.
        # unlike args, return only sends one thing.
        if builtins.is_none(insn.value().type):
            # do not waste time and bandwidth on Nones
            return

        def ret_error_handler(typ):
            printer = types.TypePrinter()
            note = diagnostic.Diagnostic("note",
                "value of type {type}",
                {"type": printer.name(typ)},
                fun_loc)
            diag = diagnostic.Diagnostic("error",
                "return type {type} is not supported in subkernel returns",
                {"type": printer.name(fun_type.ret)},
                fun_loc, notes=[note])
            self.engine.process(diag)
        tag = ir.rpc_tag(insn.value().type, ret_error_handler)
        tag += b":"
        lltag = self.llconst_of_const(ir.Constant(tag, builtins.TStr()))
        lltagptr = self.llbuilder.alloca(lltag.type)
        self.llbuilder.store(lltag, lltagptr)

        llrets = self.llbuilder.alloca(llptr, ll.Constant(lli32, 1),
                                    name="subkernel.return")    
        llret = self.map(insn.value())
        llretslot = self.llbuilder.alloca(llret.type, name="subkernel.retval")
        self.llbuilder.store(llret, llretslot)
        llretslot = self.llbuilder.bitcast(llretslot, llptr)
        self.llbuilder.store(llretslot, llrets)

        llsid = ll.Constant(lli32, 0)  # return goes back to the caller, sid is ignored
        lltagcount = ll.Constant(lli8, 1)  # only one thing is returned
        llisreturn = ll.Constant(lli1, True)  # it's a return, so destination is ignored
        lldest = ll.Constant(lli8, 0)
        self.llbuilder.call(self.llbuiltin("subkernel_send_message"),
                            [llsid, llisreturn, lldest, lltagcount, lltagptr, llrets])

    def process_Call(self, insn):
        functiontyp = insn.target_function().type
        if types.is_rpc(functiontyp):
            return self._build_rpc(insn.target_function().loc,
                                   functiontyp,
                                   insn.arguments(),
                                   llnormalblock=None, llunwindblock=None)
        elif types.is_subkernel(functiontyp):
            return self._build_subkernel_call(insn.target_function().loc,
                                              functiontyp,
                                              insn.arguments())
        elif types.is_external_function(functiontyp):
            llfun, llargs, llarg_attrs, llcallstackptr = self._prepare_ffi_call(insn)
        else:
            llfun, llargs, llarg_attrs, llcallstackptr = self._prepare_closure_call(insn)

        if self.has_sret(functiontyp):
            llstackptr = self.llbuilder.call(self.llbuiltin("llvm.stacksave"), [])

            llresultslot = self.llbuilder.alloca(llfun.type.pointee.args[0].pointee)
            self.llbuilder.call(llfun, [llresultslot] + llargs, arg_attrs=llarg_attrs)
            llresult = self.llbuilder.load(llresultslot)

            self.llbuilder.call(self.llbuiltin("llvm.stackrestore"), [llstackptr])
        else:
            llresult = self.llbuilder.call(llfun, llargs, name=insn.name,
                                           arg_attrs=llarg_attrs)

            if isinstance(llresult.type, ll.VoidType):
                # We have NoneType-returning functions return void, but None is
                # {} elsewhere.
                llresult = ll.Constant(llunit, [])

        if llcallstackptr != None:
            self.llbuilder.call(self.llbuiltin("llvm.stackrestore"), [llcallstackptr])

        return llresult

    def process_Invoke(self, insn):
        functiontyp = insn.target_function().type
        llnormalblock = self.map(insn.normal_target())
        llunwindblock = self.map(insn.exception_target())
        if types.is_rpc(functiontyp):
            return self._build_rpc(insn.target_function().loc,
                                   functiontyp,
                                   insn.arguments(),
                                   llnormalblock, llunwindblock)
        elif types.is_subkernel(functiontyp):
            return self._build_subkernel_call(insn.target_function().loc,
                                         functiontyp,
                                         insn.arguments(),
                                         llnormalblock, llunwindblock)
        elif types.is_external_function(functiontyp):
            llfun, llargs, llarg_attrs, llcallstackptr = self._prepare_ffi_call(insn)
        else:
            llfun, llargs, llarg_attrs, llcallstackptr = self._prepare_closure_call(insn)

        if self.has_sret(functiontyp):
            llstackptr = self.llbuilder.call(self.llbuiltin("llvm.stacksave"), [])

            llresultslot = self.llbuilder.alloca(llfun.type.pointee.args[0].pointee)
            llcall = self.llbuilder.invoke(llfun, [llresultslot] + llargs,
                                           llnormalblock, llunwindblock, name=insn.name,
                                           arg_attrs=llarg_attrs)

            self.llbuilder.position_at_start(llnormalblock)
            llresult = self.llbuilder.load(llresultslot)

            self.llbuilder.call(self.llbuiltin("llvm.stackrestore"), [llstackptr])
        else:
            llcall = self.llbuilder.invoke(llfun, llargs, llnormalblock, llunwindblock,
                                           name=insn.name, arg_attrs=llarg_attrs)
            llresult = llcall

            # The !tbaa metadata is not legal to use with the invoke instruction,
            # so unlike process_Call, we do not set it here.

        if llcallstackptr != None:
            self.llbuilder.call(self.llbuiltin("llvm.stackrestore"), [llcallstackptr])

        return llresult

    def _quote_listish_to_llglobal(self, value, elt_type, path, kind_name):
        fail_msg = "at " + ".".join(path())
        if len(value) > 0:
            if builtins.is_int(elt_type):
                int_typ = (int, numpy.int32, numpy.int64)
                for v in value:
                    assert isinstance(v, int_typ), fail_msg
                llty = self.llty_of_type(elt_type)
                llelts = [ll.Constant(llty, int(v)) for v in value]
            elif builtins.is_float(elt_type):
                for v in value:
                    assert isinstance(v, float), fail_msg
                llty = self.llty_of_type(elt_type)
                llelts = [ll.Constant(llty, v) for v in value]
            else:
                llelts = [self._quote(value[i], elt_type, lambda: path() + [str(i)])
                          for i in range(len(value))]
        else:
            llelts = []
        lleltsary = ll.Constant(ll.ArrayType(self.llty_of_type(elt_type), len(llelts)),
                                list(llelts))
        name = self.llmodule.scope.deduplicate("quoted.{}".format(kind_name))
        llglobal = ll.GlobalVariable(self.llmodule, lleltsary.type, name)
        llglobal.initializer = lleltsary
        llglobal.linkage = "private"
        return llglobal.bitcast(lleltsary.type.element.as_pointer())

    def _quote_attributes(self, value, typ, path, value_id, llty):
        llglobal = None
        llfields = []
        emit_as_constant = True
        for attr in typ.attributes:
            if attr == "__objectid__":
                objectid = self.embedding_map.store_object(value)
                llfields.append(ll.Constant(lli32, objectid))

                assert llglobal is None
                if types.is_constructor(typ):
                    llglobal = self.get_class(typ)
                else:
                    llglobal = ll.GlobalVariable(self.llmodule, llty.pointee,
                                                 name="O.{}".format(objectid))

                self.llobject_map[value_id] = llglobal
            else:
                attrvalue = getattr(value, attr)
                is_class_function = (types.is_constructor(typ) and
                                     types.is_function(typ.attributes[attr]) and
                                     not types.is_external_function(typ.attributes[attr]) and
                                     not types.is_subkernel(typ.attributes[attr]))
                if is_class_function:
                    attrvalue = self.embedding_map.specialize_function(typ.instance, attrvalue)
                if not (types.is_instance(typ) and attr in typ.constant_attributes):
                    emit_as_constant = False
                llattrvalue = self._quote(attrvalue, typ.attributes[attr],
                                          lambda: path() + [attr])
                llfields.append(llattrvalue)
                if is_class_function:
                    llclosureptr = self.get_global_closure_ptr(typ, attr)
                    llclosureptr.initializer = llattrvalue

        llglobal.global_constant = emit_as_constant
        llglobal.initializer = ll.Constant(llty.pointee, llfields)
        llglobal.linkage = "private"
        return llglobal

    def _quote(self, value, typ, path):
        value_id = id(value)
        if value_id in self.llobject_map:
            return self.llobject_map[value_id]
        llty = self.llty_of_type(typ)

        fail_msg = self.quote_fail_msg
        if fail_msg == None:
            self.quote_fail_msg = fail_msg = "at " + ".".join(path())

        if types.is_constructor(typ) or types.is_instance(typ):
            if types.is_instance(typ):
                # Make sure the class functions are quoted, as this has the side effect of
                # initializing the global closures.
                self._quote(type(value), typ.constructor,
                            lambda: path() + ['__class__'])
            return self._quote_attributes(value, typ, path, value_id, llty)
        elif types.is_module(typ):
            return self._quote_attributes(value, typ, path, value_id, llty)
        elif builtins.is_none(typ):
            assert value is None, fail_msg
            return ll.Constant.literal_struct([])
        elif builtins.is_bool(typ):
            assert value in (True, False), fail_msg
            # Explicitly cast to bool to handle numpy.bool_.
            return ll.Constant(llty, bool(value))
        elif builtins.is_int(typ):
            assert isinstance(value, (int, numpy.int32, numpy.int64)), fail_msg
            return ll.Constant(llty, int(value))
        elif builtins.is_float(typ):
            assert isinstance(value, float), fail_msg
            return ll.Constant(llty, value)
        elif builtins.is_str(typ) or builtins.is_bytes(typ) or builtins.is_bytearray(typ):
            assert isinstance(value, (str, bytes, bytearray)), fail_msg
            if isinstance(value, str):
                as_bytes = value.encode("utf-8")
            else:
                as_bytes = value

            llstr     = self.llstr_of_str(as_bytes)
            llconst   = ll.Constant(llty, [llstr, ll.Constant(lli32, len(as_bytes))])
            return llconst
        elif builtins.is_array(typ):
            assert isinstance(value, numpy.ndarray), fail_msg
            typ = typ.find()
            assert len(value.shape) == typ["num_dims"].find().value
            flattened = value.reshape((-1,))
            lleltsptr = self._quote_listish_to_llglobal(flattened, typ["elt"], path, "array")
            llshape = ll.Constant.literal_struct([ll.Constant(lli32, s) for s in value.shape])
            return ll.Constant(llty, [lleltsptr, llshape])
        elif builtins.is_listish(typ):
            assert isinstance(value, (list, numpy.ndarray)), fail_msg
            elt_type  = builtins.get_iterable_elt(typ)
            lleltsptr = self._quote_listish_to_llglobal(value, elt_type, path, typ.find().name)
            if builtins.is_list(typ):
                llconst   = ll.Constant(llty.pointee, [lleltsptr, ll.Constant(lli32, len(value))])
                name = self.llmodule.scope.deduplicate("quoted.{}".format(typ.find().name))
                llglobal = ll.GlobalVariable(self.llmodule, llconst.type, name)
                llglobal.initializer = llconst
                llglobal.linkage = "private"
                return llglobal
            llconst   = ll.Constant(llty, [lleltsptr, ll.Constant(lli32, len(value))])
            return llconst
        elif types.is_tuple(typ):
            assert isinstance(value, tuple), fail_msg
            llelts = [self._quote(v, t, lambda: path() + [str(i)])
                for i, (v, t) in enumerate(zip(value, typ.elts))]
            return ll.Constant(llty, llelts)
        elif types.is_rpc(typ) or types.is_external_function(typ) or \
                types.is_builtin_function(typ) or types.is_subkernel(typ):
            # RPC, C and builtin functions have no runtime representation.
            return ll.Constant(llty, ll.Undefined)
        elif types.is_function(typ):
            try:
                func = self.embedding_map.retrieve_function(value)
            except KeyError:
                # If a class function was embedded directly (e.g. by a `C.f(...)` call),
                # but it also appears in a class hierarchy, we might need to fall back
                # to the non-specialized one, since direct invocations do not cause
                # monomorphization.
                assert isinstance(value, SpecializedFunction)
                func = self.embedding_map.retrieve_function(value.host_function)
            return self.get_function_with_undef_env(typ.find(), func)
        elif types.is_method(typ):
            llclosure = self._quote(value.__func__, types.get_method_function(typ),
                                    lambda: path() + ['__func__'])
            llself    = self._quote(value.__self__, types.get_method_self(typ),
                                    lambda: path() + ['__self__'])
            return ll.Constant(llty, [llclosure, llself])
        else:
            print(typ)
            assert False, fail_msg

    def process_Quote(self, insn):
        assert self.embedding_map is not None
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
            dest = self.map(dest)
            self.add_pred(self.llbuilder.basic_block, dest)
            if dest not in self.llpred_map:
                self.llpred_map[dest] = set()
            self.llpred_map[dest].add(self.llbuilder.basic_block)
            llinsn.add_destination(dest)
        return llinsn

    def process_Return(self, insn):
        if insn.remote_return:
            self._build_subkernel_return(insn)
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

    def process_Resume(self, insn):
        return self._gen_raise(insn, self.llbuiltin("__artiq_resume"), [])

    def process_LandingPad(self, insn):
        # Layout on return from landing pad: {%_Unwind_Exception*, %Exception*}
        lllandingpadty = ll.LiteralStructType([llptr, llptr])
        lllandingpad = self.llbuilder.landingpad(lllandingpadty,
                                                 cleanup=insn.has_cleanup)
        llrawexn = self.llbuilder.extract_value(lllandingpad, 1)
        llexn = self.llbuilder.bitcast(llrawexn, self.llty_of_type(insn.type))
        llexnidptr = self.llbuilder.gep(llexn, [self.llindex(0), self.llindex(0)],
                                          inbounds=True)
        llexnid = self.llbuilder.load(llexnidptr)

        landingpadbb = self.llbuilder.basic_block
        for target, typ in insn.clauses():
            if typ is None:
                # we use a null pointer here, similar to how cpp does it
                # https://llvm.org/docs/ExceptionHandling.html#try-catch
                # > If @ExcType is null, any exception matches, so the
                # landingpad should always be entered. This is used for C++
                # catch-all blocks (“catch (...)”).
                lllandingpad.add_clause(
                    ll.CatchClause(
                        ll.Constant(lli32, 0).inttoptr(llptr)
                    )
                )

                # typ is None means that we match all exceptions, so no need to
                # compare
                target = self.map(target)
                self.add_pred(landingpadbb, target)
                self.add_pred(landingpadbb, self.llbuilder.basic_block)
                self.llbuilder.branch(target)
            else:
                exnname = "{}:{}".format(typ.id, typ.name)
                llclauseexnidptr = self.llmodule.globals.get("exn.{}".format(exnname))
                exnid = ll.Constant(lli32, self.embedding_map.store_str(exnname))
                if llclauseexnidptr is None:
                    llclauseexnidptr = ll.GlobalVariable(self.llmodule, lli32,
                                                         name="exn.{}".format(exnname))
                    llclauseexnidptr.global_constant = True
                    llclauseexnidptr.initializer = exnid
                    llclauseexnidptr.linkage = "private"
                    llclauseexnidptr.unnamed_addr = True
                lllandingpad.add_clause(ll.CatchClause(llclauseexnidptr))
                llmatchingdata = self.llbuilder.icmp_unsigned("==", llexnid,
                                                              exnid)
                with self.llbuilder.if_then(llmatchingdata):
                    target = self.map(target)
                    self.add_pred(landingpadbb, target)
                    self.add_pred(landingpadbb, self.llbuilder.basic_block)
                    self.llbuilder.branch(target)
                self.add_pred(landingpadbb, self.llbuilder.basic_block)

        if self.llbuilder.basic_block.terminator is None:
            if insn.has_cleanup:
                target = self.map(insn.cleanup())
                self.add_pred(landingpadbb, target)
                self.add_pred(landingpadbb, self.llbuilder.basic_block)
                self.llbuilder.branch(target)
            else:
                self.llbuilder.resume(lllandingpad)

        return llexn
