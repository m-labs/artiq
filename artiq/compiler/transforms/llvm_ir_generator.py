"""
:class:`LLVMIRGenerator` transforms ARTIQ intermediate representation
into LLVM intermediate representation.
"""

import os, re, types as pytypes, numpy
from collections import defaultdict
from pythonparser import ast, diagnostic
from llvmlite_artiq import ir as ll, binding as llvm
from ...language import core as language_core
from .. import types, builtins, ir
from ..embedding import SpecializedFunction


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
            "emissionKind":    2, # full=1, lines only=2
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
            "variables":       self.emit_metadata([])
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
        self.phis = []
        self.debug_info_emitter = DebugInfoEmitter(self.llmodule)
        self.empty_metadata = self.llmodule.add_metadata([])
        self.tbaa_tree = self.llmodule.add_metadata([
            ll.MetaDataString(self.llmodule, "ARTIQ TBAA")
        ])
        self.tbaa_nowrite_call = self.llmodule.add_metadata([
            ll.MetaDataString(self.llmodule, "ref-only function call"),
            self.tbaa_tree,
            ll.Constant(lli64, 1)
        ])

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
        elif types.is_rpc(typ) or types.is_c_function(typ):
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
        elif builtins.is_listish(typ):
            lleltty = self.llty_of_type(builtins.get_iterable_elt(typ))
            return ll.LiteralStructType([lleltty.as_pointer(), lli32])
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

            llptr = self.llstr_of_str(const.value, linkage="private", unnamed_addr=True)
            lllen = ll.Constant(lli32, len(const.value))
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
        elif name == "__artiq_reraise":
            llty = ll.FunctionType(llvoid, [])
        elif name in "abort":
            llty = ll.FunctionType(llvoid, [])
        elif name == "memcmp":
            llty = ll.FunctionType(lli32, [llptr, llptr, lli32])
        elif name == "rpc_send":
            llty = ll.FunctionType(llvoid, [lli32, llsliceptr, llptrptr])
        elif name == "rpc_send_async":
            llty = ll.FunctionType(llvoid, [lli32, llsliceptr, llptrptr])
        elif name == "rpc_recv":
            llty = ll.FunctionType(lli32, [llptr])
        elif name == "now":
            llty = lli64
        elif name == "watchdog_set":
            llty = ll.FunctionType(lli32, [lli64])
        elif name == "watchdog_clear":
            llty = ll.FunctionType(llvoid, [lli32])
        else:
            assert False

        if isinstance(llty, ll.FunctionType):
            llglobal = ll.Function(self.llmodule, llty, name)
            if name in ("__artiq_raise", "__artiq_reraise", "llvm.trap"):
                llglobal.attributes.add("noreturn")
            if name in ("rtio_log", "rpc_send", "rpc_send_async",
                        "watchdog_set", "watchdog_clear",
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
                    rpctag = b"Os" + self._rpc_tag(typ, error_handler=rpc_tag_error) + b":n"

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
                llblock_map[block] = self.llbuilder.basic_block

            # Fourth, add incoming values to phis.
            for phi, llphi in self.phis:
                for value, block in phi.incoming():
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
        elif builtins.is_listish(insn.type):
            llsize = self.map(insn.operands[0])
            lleltty = self.llty_of_type(builtins.get_iterable_elt(insn.type))
            llalloc = self.llbuilder.alloca(lleltty, size=llsize)
            llvalue = ll.Constant(self.llty_of_type(insn.type), ll.Undefined)
            llvalue = self.llbuilder.insert_value(llvalue, llalloc, 0, name=insn.name)
            llvalue = self.llbuilder.insert_value(llvalue, llsize, 1)
            return llvalue
        elif not builtins.is_allocated(insn.type) or ir.is_keyword(insn.type):
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
        assert types.is_function(closure_type) or types.is_rpc(closure_type)
        if types.is_c_function(closure_type) or types.is_rpc(closure_type):
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
        elif not builtins.is_allocated(typ):
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

    def process_GetElem(self, insn):
        lst, idx = insn.list(), insn.index()
        lllst, llidx = map(self.map, (lst, idx))
        llelts = self.llbuilder.extract_value(lllst, 0)
        llelt = self.llbuilder.gep(llelts, [llidx], inbounds=True)
        llvalue = self.llbuilder.load(llelt)
        if isinstance(llvalue.type, ll.PointerType):
            self.mark_dereferenceable(llvalue)
        return llvalue

    def process_SetElem(self, insn):
        lst, idx = insn.list(), insn.index()
        lllst, llidx = map(self.map, (lst, idx))
        llelts = self.llbuilder.extract_value(lllst, 0)
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
        if insn.op == "abort":
            return self.llbuilder.call(self.llbuiltin("abort"), [])
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
            llnow = self.llbuilder.load(self.llbuiltin("now"), name=insn.name)
            return llnow
        elif insn.op == "at_mu":
            time, = insn.operands
            lltime = self.map(time)
            lltime_hi = self.llbuilder.trunc(self.llbuilder.lshr(lltime, ll.Constant(lli64, 32)), lli32)
            lltime_lo = self.llbuilder.trunc(lltime, lli32)
            llnow_hiptr = self.llbuilder.bitcast(self.llbuiltin("now"), lli32.as_pointer())
            llnow_loptr = self.llbuilder.gep(llnow_hiptr, [self.llindex(1)])
            if self.target.little_endian:
                lltime_hi, lltime_lo = lltime_lo, lltime_hi
            llstore_hi = self.llbuilder.store_atomic(lltime_hi, llnow_hiptr, ordering="seq_cst", align=4)
            llstore_lo = self.llbuilder.store_atomic(lltime_lo, llnow_loptr, ordering="seq_cst", align=4)
            return llstore_lo
        elif insn.op == "delay_mu":
            interval, = insn.operands
            llnowptr = self.llbuiltin("now")
            llnow = self.llbuilder.load(llnowptr, name="now.old")
            lladjusted = self.llbuilder.add(llnow, self.map(interval), name="now.new")

            lladjusted_hi = self.llbuilder.trunc(self.llbuilder.lshr(lladjusted, ll.Constant(lli64, 32)), lli32)
            lladjusted_lo = self.llbuilder.trunc(lladjusted, lli32)
            llnow_hiptr = self.llbuilder.bitcast(llnowptr, lli32.as_pointer())
            llnow_loptr = self.llbuilder.gep(llnow_hiptr, [self.llindex(1)])
            if self.target.little_endian:
                lladjusted_hi, lladjusted_lo = lladjusted_lo, lladjusted_hi
            llstore_hi = self.llbuilder.store_atomic(lladjusted_hi, llnow_hiptr, ordering="seq_cst", align=4)
            llstore_lo = self.llbuilder.store_atomic(lladjusted_lo, llnow_loptr, ordering="seq_cst", align=4)
            return llstore_lo
        elif insn.op == "watchdog_set":
            interval, = insn.operands
            return self.llbuilder.call(self.llbuiltin("watchdog_set"), [self.map(interval)])
        elif insn.op == "watchdog_clear":
            id, = insn.operands
            return self.llbuilder.call(self.llbuiltin("watchdog_clear"), [self.map(id)])
        else:
            assert False

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
        llfun     = self.llmodule.globals.get(llfunname)
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
            if 'nounwind' in insn.target_function().type.flags:
                llfun.attributes.add('nounwind')

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
        elif builtins.is_bytes(typ):
            return b"B"
        elif builtins.is_bytearray(typ):
            return b"A"
        elif builtins.is_list(typ):
            return b"l" + self._rpc_tag(builtins.get_iterable_elt(typ),
                                        error_handler)
        elif builtins.is_array(typ):
            return b"a" + self._rpc_tag(builtins.get_iterable_elt(typ),
                                        error_handler)
        elif builtins.is_range(typ):
            return b"r" + self._rpc_tag(builtins.get_iterable_elt(typ),
                                        error_handler)
        elif ir.is_keyword(typ):
            return b"k" + self._rpc_tag(typ.params["value"],
                                        error_handler)
        elif types.is_function(typ) or types.is_method(typ) or types.is_rpc(typ):
            raise ValueError("RPC tag for functional value")
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

        lltag = self.llconst_of_const(ir.Constant(tag, builtins.TStr()))
        lltagptr = self.llbuilder.alloca(lltag.type)
        self.llbuilder.store(lltag, lltagptr)

        llstackptr = self.llbuilder.call(self.llbuiltin("llvm.stacksave"), [],
                                         name="rpc.stack")

        llargs = self.llbuilder.alloca(llptr, ll.Constant(lli32, len(args)),
                                       name="rpc.args")
        for index, arg in enumerate(args):
            if builtins.is_none(arg.type):
                llargslot = self.llbuilder.alloca(ll.LiteralStructType([]),
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

        llretty = self.llty_of_type(fun_type.ret)
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
        llalloca.align = 4 # maximum alignment required by OR1K ABI
        llphi.add_incoming(llalloca, llalloc)
        self.llbuilder.branch(llhead)

        self.llbuilder.position_at_end(lltail)
        llret = self.llbuilder.load(llslot, name="rpc.ret")
        if not fun_type.ret.fold(False, lambda r, t: r or builtins.is_allocated(t)):
            # We didn't allocate anything except the slot for the value itself.
            # Don't waste stack space.
            self.llbuilder.call(self.llbuiltin("llvm.stackrestore"), [llstackptr])
        if llnormalblock:
            self.llbuilder.branch(llnormalblock)
        return llret

    def process_Call(self, insn):
        functiontyp = insn.target_function().type
        if types.is_rpc(functiontyp):
            return self._build_rpc(insn.target_function().loc,
                                   functiontyp,
                                   insn.arguments(),
                                   llnormalblock=None, llunwindblock=None)
        elif types.is_c_function(functiontyp):
            llfun, llargs = self._prepare_ffi_call(insn)
        else:
            llfun, llargs = self._prepare_closure_call(insn)

        if self.has_sret(functiontyp):
            llstackptr = self.llbuilder.call(self.llbuiltin("llvm.stacksave"), [])

            llresultslot = self.llbuilder.alloca(llfun.type.pointee.args[0].pointee)
            llcall = self.llbuilder.call(llfun, [llresultslot] + llargs)
            llresult = self.llbuilder.load(llresultslot)

            self.llbuilder.call(self.llbuiltin("llvm.stackrestore"), [llstackptr])
        else:
            llcall = llresult = self.llbuilder.call(llfun, llargs, name=insn.name)

            # Never add TBAA nowrite metadata to a functon with sret!
            # This leads to miscompilations.
            if types.is_c_function(functiontyp) and 'nowrite' in functiontyp.flags:
                llcall.set_metadata('tbaa', self.tbaa_nowrite_call)

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
        elif types.is_c_function(functiontyp):
            llfun, llargs = self._prepare_ffi_call(insn)
        else:
            llfun, llargs = self._prepare_closure_call(insn)

        if self.has_sret(functiontyp):
            llstackptr = self.llbuilder.call(self.llbuiltin("llvm.stacksave"), [])

            llresultslot = self.llbuilder.alloca(llfun.type.pointee.args[0].pointee)
            llcall = self.llbuilder.invoke(llfun, llargs, llnormalblock, llunwindblock,
                                           name=insn.name)
            llresult = self.llbuilder.load(llresultslot)

            self.llbuilder.call(self.llbuiltin("llvm.stackrestore"), [llstackptr])
        else:
            llcall = self.llbuilder.invoke(llfun, llargs, llnormalblock, llunwindblock,
                                           name=insn.name)

            # The !tbaa metadata is not legal to use with the invoke instruction,
            # so unlike process_Call, we do not set it here.

        return llcall

    def _quote(self, value, typ, path):
        value_id = id(value)
        if value_id in self.llobject_map:
            return self.llobject_map[value_id]
        llty = self.llty_of_type(typ)

        def _quote_attributes():
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
                                         not types.is_c_function(typ.attributes[attr]))
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

        fail_msg = "at " + ".".join(path())
        if types.is_constructor(typ) or types.is_instance(typ):
            if types.is_instance(typ):
                # Make sure the class functions are quoted, as this has the side effect of
                # initializing the global closures.
                self._quote(type(value), typ.constructor,
                            lambda: path() + ['__class__'])
            return _quote_attributes()
        elif types.is_module(typ):
            return _quote_attributes()
        elif builtins.is_none(typ):
            assert value is None, fail_msg
            return ll.Constant.literal_struct([])
        elif builtins.is_bool(typ):
            assert value in (True, False), fail_msg
            return ll.Constant(llty, value)
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
        elif builtins.is_listish(typ):
            assert isinstance(value, (list, numpy.ndarray)), fail_msg
            elt_type  = builtins.get_iterable_elt(typ)
            llelts    = [self._quote(value[i], elt_type, lambda: path() + [str(i)])
                         for i in range(len(value))]
            lleltsary = ll.Constant(ll.ArrayType(self.llty_of_type(elt_type), len(llelts)),
                                    list(llelts))

            name      = self.llmodule.scope.deduplicate("quoted.{}".format(typ.name))
            llglobal  = ll.GlobalVariable(self.llmodule, lleltsary.type, name)
            llglobal.initializer = lleltsary
            llglobal.linkage = "private"

            lleltsptr = llglobal.bitcast(lleltsary.type.element.as_pointer())
            llconst   = ll.Constant(llty, [lleltsptr, ll.Constant(lli32, len(llelts))])
            return llconst
        elif types.is_tuple(typ):
            assert isinstance(value, tuple), fail_msg
            llelts = [self._quote(v, t, lambda: path() + [str(i)])
                for i, (v, t) in enumerate(zip(value, typ.elts))]
            return ll.Constant(llty, llelts)
        elif types.is_rpc(typ) or types.is_c_function(typ) or types.is_builtin_function(typ):
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
        lllandingpad = self.llbuilder.landingpad(lllandingpadty, cleanup=True)
        llrawexn = self.llbuilder.extract_value(lllandingpad, 1)
        llexn = self.llbuilder.bitcast(llrawexn, self.llty_of_type(insn.type))
        llexnnameptr = self.llbuilder.gep(llexn, [self.llindex(0), self.llindex(0)],
                                          inbounds=True)
        llexnname = self.llbuilder.load(llexnnameptr)

        for target, typ in insn.clauses():
            if typ is None:
                exnname = "" # see the comment in ksupport/eh.rs
            else:
                exnname = "{}:{}".format(typ.id, typ.name)

            llclauseexnname = self.llconst_of_const(
                ir.Constant(exnname, builtins.TStr()))
            llclauseexnnameptr = self.llmodule.globals.get("exn.{}".format(exnname))
            if llclauseexnnameptr is None:
                llclauseexnnameptr = ll.GlobalVariable(self.llmodule, llclauseexnname.type,
                                                       name="exn.{}".format(exnname))
                llclauseexnnameptr.global_constant = True
                llclauseexnnameptr.initializer = llclauseexnname
                llclauseexnnameptr.linkage = "private"
                llclauseexnnameptr.unnamed_addr = True
            lllandingpad.add_clause(ll.CatchClause(llclauseexnnameptr))

            if typ is None:
                self.llbuilder.branch(self.map(target))
            else:
                llexnlen       = self.llbuilder.extract_value(llexnname, 1)
                llclauseexnlen = self.llbuilder.extract_value(llclauseexnname, 1)
                llmatchinglen  = self.llbuilder.icmp_unsigned('==', llexnlen, llclauseexnlen)
                with self.llbuilder.if_then(llmatchinglen):
                    llexnptr       = self.llbuilder.extract_value(llexnname, 0)
                    llclauseexnptr = self.llbuilder.extract_value(llclauseexnname, 0)
                    llcomparedata  = self.llbuilder.call(self.llbuiltin("memcmp"),
                                                         [llexnptr, llclauseexnptr, llexnlen])
                    llmatchingdata = self.llbuilder.icmp_unsigned('==', llcomparedata,
                                                                  ll.Constant(lli32, 0))
                    with self.llbuilder.if_then(llmatchingdata):
                        self.llbuilder.branch(self.map(target))

        if self.llbuilder.basic_block.terminator is None:
            self.llbuilder.branch(self.map(insn.cleanup()))

        return llexn
