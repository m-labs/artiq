from operator import itemgetter

from artiq.language.db import AutoDB
from artiq.language.units import ms
from artiq.coredevice.runtime import LinkInterface


class _RuntimeEnvironment(LinkInterface):
    def __init__(self):
        self.warmup_time = 1*ms

    def emit_object(self):
        return str(self.llvm_module)


class Comm(AutoDB):
    def get_runtime_env(self):
        return _RuntimeEnvironment()

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
