import sys, os

from artiq.master.databases import DeviceDB
from artiq.master.worker_db import DeviceManager

from artiq.coredevice.core import Core, CompileError

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "+compile":
        del sys.argv[1]
        compile_only = True
    else:
        compile_only = False

    with open(sys.argv[1]) as f:
        testcase_code = compile(f.read(), f.name, "exec")
        testcase_vars = {'__name__': 'testbench'}
        exec(testcase_code, testcase_vars)

    ddb_path = os.path.join(os.path.dirname(sys.argv[1]), "device_db.pyon")

    try:
        core = DeviceManager(DeviceDB(ddb_path)).get("core")
        if compile_only:
            core.compile(testcase_vars["entrypoint"], (), {})
        else:
            core.run(testcase_vars["entrypoint"], (), {})
            print(core.comm.get_log())
            core.comm.clear_log()
    except CompileError as error:
        print("\n".join(error.__cause__.diagnostic.render(only_line=True)))

if __name__ == "__main__":
    main()
