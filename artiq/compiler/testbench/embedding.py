import sys, os, tokenize

from artiq.master.databases import DeviceDB
from artiq.master.worker_db import DeviceManager

import artiq.coredevice.core
from artiq.coredevice.core import Core, CompileError

def _render_diagnostic(diagnostic, colored):
    return "\n".join(diagnostic.render(only_line=True))

artiq.coredevice.core._render_diagnostic = _render_diagnostic

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "+diag":
        del sys.argv[1]
        diag = True
    else:
        diag = False

    if len(sys.argv) > 1 and sys.argv[1] == "+compile":
        del sys.argv[1]
        compile_only = True
    else:
        compile_only = False

    ddb_path = os.path.join(os.path.dirname(sys.argv[1]), "device_db.py")
    dmgr = DeviceManager(DeviceDB(ddb_path))

    with tokenize.open(sys.argv[1]) as f:
        testcase_code = compile(f.read(), f.name, "exec")
        testcase_vars = {'__name__': 'testbench', 'dmgr': dmgr}
        exec(testcase_code, testcase_vars)

    try:
        core = dmgr.get("core")
        if compile_only:
            core.compile(testcase_vars["entrypoint"], (), {})
        else:
            core.run(testcase_vars["entrypoint"], (), {})
    except CompileError as error:
        if not diag:
            exit(1)

if __name__ == "__main__":
    main()
