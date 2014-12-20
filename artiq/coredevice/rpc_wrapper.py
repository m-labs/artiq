from artiq.coredevice.runtime_exceptions import exception_map, _RPCException


def _lookup_exception(d, e):
    for eid, exception in d.items():
        if isinstance(e, exception):
            return eid
    return 0


class RPCWrapper:
    def __init__(self):
        self.last_exception = None

    def run_rpc(self, user_exception_map, fn, args):
        eid = 0
        r = None

        try:
            r = fn(*args)
        except Exception as e:
            eid = _lookup_exception(user_exception_map, e)
            if not eid:
                eid = _lookup_exception(exception_map, e)
            if eid:
                self.last_exception = None
            else:
                self.last_exception = e
                eid = _RPCException.eid

        if r is None:
            r = 0
        else:
            r = int(r)

        return eid, r

    def filter_rpc_exception(self, eid):
        if eid == _RPCException.eid:
            raise self.last_exception
