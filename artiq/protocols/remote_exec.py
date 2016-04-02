from functools import partial
import inspect

from artiq.protocols.pc_rpc import simple_server_loop


__all__ = ["RemoteExecServer", "RemoteExecClient", "simple_rexec_server_loop"]


class RemoteExecServer:
    def __init__(self, initial_namespace):
        self.namespace = dict(initial_namespace)

    def add_code(self, code):
        exec(code, self.namespace)

    def call(self, function, *args, **kwargs):
        return self.namespace[function](*args, **kwargs)


def simple_rexec_server_loop(target_name, target, host, port,
                             description=None):
    initial_namespace = {"controller_driver": target}
    targets = {
        target_name: target,
        target_name + "_rexec": lambda: RemoteExecServer(initial_namespace)
    }
    simple_server_loop(targets, host, port, description)
