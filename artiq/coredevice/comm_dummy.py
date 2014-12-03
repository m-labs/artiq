from operator import itemgetter

from artiq.language.context import AutoContext
from artiq.language.units import ms, ns
from artiq.coredevice.runtime import LinkInterface


class _RuntimeEnvironment(LinkInterface):
    def __init__(self, ref_period):
        self.internal_ref_period = ref_period
        self.warmup_time = 1*ms

    def emit_object(self):
        return str(self.llvm_module)


class Comm(AutoContext):
    implicit_core = False

    def get_runtime_env(self):
        return _RuntimeEnvironment(1*ns)

    def switch_clock(self, external):
        pass

    def load(self, kcode):
        print("================")
        print(" LLVM IR")
        print("================")
        print(kcode)

    def run(self, kname):
        print("RUN: "+kname)

    def serve(self, rpc_map, exception_map):
        print("================")
        print(" RPC map")
        print("================")
        for k, v in sorted(rpc_map.items(), key=itemgetter(0)):
            print(str(k)+" -> "+str(v))
        print("================")
        print(" Exception map")
        print("================")
        for k, v in sorted(exception_map.items(), key=itemgetter(0)):
            print(str(k)+" -> "+str(v))
