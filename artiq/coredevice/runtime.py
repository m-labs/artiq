import os

import llvmlite.ir as ll
import llvmlite.binding as llvm

from artiq.py2llvm import base_types
from artiq.language import units


llvm.initialize()
llvm.initialize_all_targets()
llvm.initialize_all_asmprinters()

_syscalls = {
    "rpc": "i+:i",
    "gpio_set": "ib:n",
    "rtio_oe": "ib:n",
    "rtio_set": "Iii:n",
    "rtio_get_counter": "n:I",
    "rtio_get": "iI:I",
    "rtio_pileup_count": "i:i",
    "dds_phase_clear_en": "ib:n",
    "dds_program": "Iiiiibb:n",
}

_chr_to_type = {
    "n": lambda: ll.VoidType(),
    "b": lambda: ll.IntType(1),
    "i": lambda: ll.IntType(32),
    "I": lambda: ll.IntType(64)
}

_chr_to_value = {
    "n": lambda: base_types.VNone(),
    "b": lambda: base_types.VBool(),
    "i": lambda: base_types.VInt(),
    "I": lambda: base_types.VInt(64)
}


def _str_to_functype(s):
    assert(s[-2] == ":")
    type_ret = _chr_to_type[s[-1]]()

    var_arg_fixcount = None
    type_args = []
    for n, c in enumerate(s[:-2]):
        if c == "+":
            type_args.append(ll.IntType(32))
            var_arg_fixcount = n
        elif c != "n":
            type_args.append(_chr_to_type[c]())
    return (var_arg_fixcount,
            ll.FunctionType(type_ret, type_args,
                            var_arg=var_arg_fixcount is not None))


class LinkInterface:
    def init_module(self, module):
        self.module = module
        llvm_module = self.module.llvm_module

        # syscalls
        self.syscalls = dict()
        self.var_arg_fixcount = dict()
        for func_name, func_type_str in _syscalls.items():
            var_arg_fixcount, func_type = _str_to_functype(func_type_str)
            if var_arg_fixcount is not None:
                self.var_arg_fixcount[func_name] = var_arg_fixcount
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

    def build_syscall(self, syscall_name, args, builder):
        r = _chr_to_value[_syscalls[syscall_name][-1]]()
        if builder is not None:
            args = [arg.auto_load(builder) for arg in args]
            if syscall_name in self.var_arg_fixcount:
                fixcount = self.var_arg_fixcount[syscall_name]
                args = args[:fixcount] \
                    + [ll.Constant(ll.IntType(32), len(args) - fixcount)] \
                    + args[fixcount:]
            r.auto_store(builder, builder.call(self.syscalls[syscall_name],
                                               args))
        return r

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


class Environment(LinkInterface):
    def __init__(self, internal_ref_period):
        self.cpu_type = "or1k"
        self.internal_ref_period = internal_ref_period
        # allow 1ms for all initial DDS programming
        self.warmup_time = 1*units.ms

    def emit_object(self):
        tm = llvm.Target.from_triple(self.cpu_type).create_target_machine()
        obj = tm.emit_object(self.module.llvm_module_ref)
        _debug_dump_obj(obj)
        return obj

    def __repr__(self):
        return "<Environment {} {}>".format(self.cpu_type,
                                            str(1/self.ref_period))
