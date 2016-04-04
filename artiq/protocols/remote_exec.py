from functools import partial
import inspect

from artiq.protocols.pc_rpc import simple_server_loop


__all__ = ["RemoteExecServer", "simple_rexec_server_loop", "connect_global_rpc"]


class RemoteExecServer:
    def __init__(self, initial_namespace):
        self.namespace = dict(initial_namespace)
        # The module actually has to exist, otherwise it breaks e.g. Numba
        self.namespace["__name__"] = "artiq.protocols.remote_exec"

    def add_code(self, code):
        exec(code, self.namespace)

    def call(self, function, *args, **kwargs):
        return self.namespace[function](*args, **kwargs)


def simple_rexec_server_loop(target_name, target, host, port,
                             description=None):
    initial_namespace = {"controller_driver": target}
    initial_namespace["controller_initial_namespace"] = initial_namespace
    targets = {
        target_name: target,
        target_name + "_rexec": lambda: RemoteExecServer(initial_namespace)
    }
    simple_server_loop(targets, host, port, description)


def connect_global_rpc(controller_rexec, host=None, port=3251,
                       target="master_dataset_db", name="dataset_db"):
    if host is None:
        host = controller_rexec.get_local_host()
    code = """
if "{name}" not in controller_initial_namespace:
    import atexit
    from artiq.protocols.pc_rpc import Client

    {name} = Client("{host}", {port}, "{target}")
    atexit.register({name}.close_rpc)
    controller_initial_namespace["{name}"] = {name}
""".format(host=host, port=port, target=target, name=name)
    controller_rexec.add_code(code)
