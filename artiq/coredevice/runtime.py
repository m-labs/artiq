import os

import llvmlite_or1k.ir as ll
import llvmlite_or1k.binding as llvm

from artiq.py2llvm import base_types, fractions, lists
from artiq.language import units


llvm.initialize()
llvm.initialize_all_targets()
llvm.initialize_all_asmprinters()

_syscalls = {
    "now_init": "n:I",
    "now_save": "I:n",
    "watchdog_set": "i:i",
    "watchdog_clear": "i:n",
    "rtio_get_counter": "n:I",
    "ttl_set_o": "Iib:n",
    "ttl_set_oe": "Iib:n",
    "ttl_set_sensitivity": "Iii:n",
    "ttl_get": "iI:I",
    "ttl_clock_set": "Iii:n",
    "dds_init": "Ii:n",
    "dds_batch_enter": "I:n",
    "dds_batch_exit": "n:n",
    "dds_set": "Iiiii:n",
}


def _chr_to_type(c):
    if c == "n":
        return ll.VoidType()
    if c == "b":
        return ll.IntType(1)
    if c == "i":
        return ll.IntType(32)
    if c == "I":
        return ll.IntType(64)
    raise ValueError


def _str_to_functype(s):
    assert(s[-2] == ":")
    type_ret = _chr_to_type(s[-1])
    type_args = [_chr_to_type(c) for c in s[:-2] if c != "n"]
    return ll.FunctionType(type_ret, type_args)


def _chr_to_value(c):
    if c == "n":
        return base_types.VNone()
    if c == "b":
        return base_types.VBool()
    if c == "i":
        return base_types.VInt()
    if c == "I":
        return base_types.VInt(64)
    raise ValueError


def _value_to_str(v):
    if isinstance(v, base_types.VNone):
        return "n"
    if isinstance(v, base_types.VBool):
        return "b"
    if isinstance(v, base_types.VInt):
        if v.nbits == 32:
            return "i"
        if v.nbits == 64:
            return "I"
        raise ValueError
    if isinstance(v, base_types.VFloat):
        return "f"
    if isinstance(v, fractions.VFraction):
        return "F"
    if isinstance(v, lists.VList):
        return "l" + _value_to_str(v.el_type)
    raise ValueError


class LinkInterface:
    def init_module(self, module):
        self.module = module
        llvm_module = self.module.llvm_module

        # RPC
        func_type = ll.FunctionType(ll.IntType(32), [ll.IntType(32)],
                                    var_arg=1)
        self.rpc = ll.Function(llvm_module, func_type, "__syscall_rpc")

        # syscalls
        self.syscalls = dict()
        for func_name, func_type_str in _syscalls.items():
            func_type = _str_to_functype(func_type_str)
            self.syscalls[func_name] = ll.Function(
                llvm_module, func_type, "__syscall_" + func_name)

        # exception handling
        func_type = ll.FunctionType(ll.IntType(32),
                                    [ll.PointerType(ll.IntType(8))])
        self.eh_setjmp = ll.Function(llvm_module, func_type,
                                     "__eh_setjmp")
        self.eh_setjmp.attributes.add("nounwind")
        self.eh_setjmp.attributes.add("returns_twice")

        func_type = ll.FunctionType(ll.PointerType(ll.IntType(8)), [])
        self.eh_push = ll.Function(llvm_module, func_type, "__eh_push")

        func_type = ll.FunctionType(ll.VoidType(), [ll.IntType(32)])
        self.eh_pop = ll.Function(llvm_module, func_type, "__eh_pop")

        func_type = ll.FunctionType(ll.IntType(32), [])
        self.eh_getid = ll.Function(llvm_module, func_type, "__eh_getid")

        func_type = ll.FunctionType(ll.VoidType(), [ll.IntType(32)])
        self.eh_raise = ll.Function(llvm_module, func_type, "__eh_raise")
        self.eh_raise.attributes.add("noreturn")

    def _build_rpc(self, args, builder):
        r = base_types.VInt()
        if builder is not None:
            new_args = []
            new_args.append(args[0].auto_load(builder))  # RPC number
            for arg in args[1:]:
                # type tag
                arg_type_str = _value_to_str(arg)
                arg_type_int = 0
                for c in reversed(arg_type_str):
                    arg_type_int <<= 8
                    arg_type_int |= ord(c)
                new_args.append(ll.Constant(ll.IntType(32), arg_type_int))

                # pointer to value
                if not isinstance(arg, base_types.VNone):
                    if isinstance(arg.llvm_value.type, ll.PointerType):
                        new_args.append(arg.llvm_value)
                    else:
                        arg_ptr = arg.new()
                        arg_ptr.alloca(builder)
                        arg_ptr.auto_store(builder, arg.llvm_value)
                        new_args.append(arg_ptr.llvm_value)
            # end marker
            new_args.append(ll.Constant(ll.IntType(32), 0))
            r.auto_store(builder, builder.call(self.rpc, new_args))
        return r

    def _build_regular_syscall(self, syscall_name, args, builder):
        r = _chr_to_value(_syscalls[syscall_name][-1])
        if builder is not None:
            args = [arg.auto_load(builder) for arg in args]
            r.auto_store(builder, builder.call(self.syscalls[syscall_name],
                                               args))
        return r

    def build_syscall(self, syscall_name, args, builder):
        if syscall_name == "rpc":
            return self._build_rpc(args, builder)
        else:
            return self._build_regular_syscall(syscall_name, args, builder)

    def build_catch(self, builder):
        jmpbuf = builder.call(self.eh_push, [])
        exception_occured = builder.call(self.eh_setjmp, [jmpbuf])
        return builder.icmp_signed("!=",
                                   exception_occured,
                                   ll.Constant(ll.IntType(32), 0))

    def build_pop(self, builder, levels):
        builder.call(self.eh_pop, [ll.Constant(ll.IntType(32), levels)])

    def build_getid(self, builder):
        return builder.call(self.eh_getid, [])

    def build_raise(self, builder, eid):
        builder.call(self.eh_raise, [eid])


def _debug_dump_obj(obj):
    try:
        env = os.environ["ARTIQ_DUMP_OBJECT"]
    except KeyError:
        return

    for i in range(1000):
        filename = "{}_{:03d}.elf".format(env, i)
        try:
            f = open(filename, "xb")
        except FileExistsError:
            pass
        else:
            f.write(obj)
            f.close()
            return
    raise IOError


class Runtime(LinkInterface):
    def __init__(self):
        self.cpu_type = "or1k"
        # allow 1ms for all initial DDS programming
        self.warmup_time = 1*units.ms

    def emit_object(self):
        tm = llvm.Target.from_triple(self.cpu_type).create_target_machine()
        obj = tm.emit_object(self.module.llvm_module_ref)
        _debug_dump_obj(obj)
        return obj

    def __repr__(self):
        return "<Runtime {}>".format(self.cpu_type)
