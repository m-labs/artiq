class RuntimeException(Exception):
    pass


class OutOfMemory(RuntimeException):
    eid = 0


class RTIOUnderflow(RuntimeException):
    eid = 1


exception_map = {e.eid: e for e in globals().values()
                 if isinstance(e, RuntimeException.__class__)
                 and hasattr(e, "eid")}
