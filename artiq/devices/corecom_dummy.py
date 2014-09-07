from operator import itemgetter

from artiq.devices.runtime import LinkInterface
from artiq.language.units import ns


class _RuntimeEnvironment(LinkInterface):
    def __init__(self, ref_period):
        self.ref_period = ref_period

    def emit_object(self):
        return str(self.llvm_module)


class CoreCom:
    def get_runtime_env(self):
        return _RuntimeEnvironment(10*ns)

    def run(self, kcode):
        print("================")
        print(" LLVM IR")
        print("================")
        print(kcode)

    def serve(self, rpc_map):
        print("================")
        print(" RPC map")
        print("================")
        for k, v in sorted(rpc_map.items(), key=itemgetter(0)):
            print(str(k)+" -> "+str(v))
