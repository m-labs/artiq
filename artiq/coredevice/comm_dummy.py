from operator import itemgetter


class Comm:
    def __init__(self, dmgr):
        pass

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
