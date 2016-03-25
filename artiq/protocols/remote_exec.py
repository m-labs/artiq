from functools import partial
import inspect

from artiq.protocols.pc_rpc import simple_server_loop
from artiq.protocols.pc_rpc import Client as RPCClient


__all__ = ["RemoteExecServer", "RemoteExecClient", "simple_rexec_server_loop"]


class RemoteExecServer:
    def __init__(self, target):
        self.target = target
        self.namespace = dict()

    def add_code(self, code):
        exec(code, self.namespace)

    def call(self, function, *args, **kwargs):
        return self.namespace[function](self, *args, **kwargs)


class RemoteExecClient(RPCClient):
    def transfer_obj_source(self, obj):
        self.add_code(self, inspect.getsource(obj))


def simple_rexec_server_loop(target_name, target, host, port,
                             description=None):
    targets = {
        target_name: target,
        target_name + "_rexec": lambda: RemoteExecServer(target)
    }
    simple_server_loop(targets, host, port, description)
