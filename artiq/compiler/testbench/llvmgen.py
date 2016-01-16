import sys, fileinput
from pythonparser import diagnostic
from llvmlite_artiq import ir as ll
from ..module import Module, Source
from ..targets import NativeTarget

def main():
    def process_diagnostic(diag):
        print("\n".join(diag.render()))
        if diag.level in ("fatal", "error"):
            exit(1)

    engine = diagnostic.Engine()
    engine.process = process_diagnostic

    mod = Module(Source.from_string("".join(fileinput.input()).expandtabs(), engine=engine))

    target = NativeTarget()
    llmod = mod.build_llvm_ir(target=target)

    # Add main so that the result can be executed with lli
    llmain = ll.Function(llmod, ll.FunctionType(ll.VoidType(), []), "main")
    llbuilder = ll.IRBuilder(llmain.append_basic_block("entry"))
    llbuilder.call(llmod.get_global(llmod.name + ".__modinit__"), [
                    ll.Constant(ll.IntType(8).as_pointer(), None)])
    llbuilder.ret_void()

    print(llmod)

if __name__ == "__main__":
    main()
