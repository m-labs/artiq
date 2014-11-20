from operator import itemgetter
from fractions import Fraction

from artiq.coredevice.runtime import LinkInterface


class _RuntimeEnvironment(LinkInterface):
    def __init__(self, ref_period):
        self.ref_period = ref_period
        self.initial_time = 0

    def emit_object(self):
        return str(self.llvm_module)


class Comm:
    def get_runtime_env(self):
        return _RuntimeEnvironment(Fraction(1, 1000000000))

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
