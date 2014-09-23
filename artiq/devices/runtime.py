import os

from llvm import core as lc
from llvm import target as lt

from artiq.py2llvm import base_types


lt.initialize_all()

_syscalls = {
    "rpc": "i+:i",
    "gpio_set": "ii:n",
    "rtio_oe": "ii:n",
    "rtio_set": "Iii:n",
    "rtio_replace": "Iii:n",
    "rtio_sync": "i:n",
    "rtio_get": "i:I",
    "dds_program": "iiI:n",
}

_chr_to_type = {
    "n": lambda: lc.Type.void(),
    "i": lambda: lc.Type.int(32),
    "I": lambda: lc.Type.int(64)
}

_chr_to_value = {
    "n": lambda: base_types.VNone(),
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
            type_args.append(lc.Type.int())
            var_arg_fixcount = n
        else:
            type_args.append(_chr_to_type[c]())
    return (var_arg_fixcount,
            lc.Type.function(type_ret, type_args,
                             var_arg=var_arg_fixcount is not None))


class LinkInterface:
    def init_module(self, module):
        self.llvm_module = module.llvm_module

        # syscalls
        self.var_arg_fixcount = dict()
        for func_name, func_type_str in _syscalls.items():
            var_arg_fixcount, func_type = _str_to_functype(func_type_str)
            if var_arg_fixcount is not None:
                self.var_arg_fixcount[func_name] = var_arg_fixcount
            self.llvm_module.add_function(func_type, "__syscall_"+func_name)

        # exception handling
        func_type = lc.Type.function(lc.Type.int(), [lc.Type.pointer(lc.Type.int(8))])
        function = self.llvm_module.add_function(func_type, "__eh_setjmp")
        function.add_attribute(lc.ATTR_NO_UNWIND)

        func_type = lc.Type.function(lc.Type.pointer(lc.Type.int(8)), [])
        self.llvm_module.add_function(func_type, "__eh_push")

        func_type = lc.Type.function(lc.Type.void(), [lc.Type.int()])
        self.llvm_module.add_function(func_type, "__eh_pop")

        func_type = lc.Type.function(lc.Type.int(), [])
        self.llvm_module.add_function(func_type, "__eh_getid")

        func_type = lc.Type.function(lc.Type.void(), [lc.Type.int()])
        function = self.llvm_module.add_function(func_type, "__eh_raise")
        function.add_attribute(lc.ATTR_NO_RETURN)

    def build_syscall(self, syscall_name, args, builder):
        r = _chr_to_value[_syscalls[syscall_name][-1]]()
        if builder is not None:
            args = [arg.auto_load(builder) for arg in args]
            if syscall_name in self.var_arg_fixcount:
                fixcount = self.var_arg_fixcount[syscall_name]
                args = args[:fixcount] \
                    + [lc.Constant.int(lc.Type.int(), len(args) - fixcount)] \
                    + args[fixcount:]
            llvm_function = self.llvm_module.get_function_named(
                "__syscall_" + syscall_name)
            r.auto_store(builder, builder.call(llvm_function, args))
        return r

    def build_catch(self, builder):
        eh_setjmp = self.llvm_module.get_function_named("__eh_setjmp")
        eh_push = self.llvm_module.get_function_named("__eh_push")
        jmpbuf = builder.call(eh_push, [])
        exception_occured = builder.call(eh_setjmp, [jmpbuf])
        return builder.icmp(lc.ICMP_NE,
                            exception_occured,
                            lc.Constant.int(lc.Type.int(), 0))

    def build_pop(self, builder, levels):
        eh_pop = self.llvm_module.get_function_named("__eh_pop")
        builder.call(eh_pop, [lc.Constant.int(lc.Type.int(), levels)])

    def build_getid(self, builder):
        eh_getid = self.llvm_module.get_function_named("__eh_getid")
        return builder.call(eh_getid, [])

    def build_raise(self, builder, eid):
        eh_raise = self.llvm_module.get_function_named("__eh_raise")
        builder.call(eh_raise, [eid])


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
    def __init__(self, ref_period):
        self.ref_period = ref_period
        self.initial_time = 4000

    def emit_object(self):
        tm = lt.TargetMachine.new(triple="or1k", cpu="generic")
        obj = tm.emit_object(self.llvm_module)
        _debug_dump_obj(obj)
        return obj
