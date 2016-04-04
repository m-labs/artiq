import inspect
import builtins
import traceback
import sys


__all__ = ["GenericRemoteException", "current_exc_packed", "raise_packed_exc"]


class GenericRemoteException(Exception):
    pass


builtin_exceptions = {v: k for k, v in builtins.__dict__.items()
                      if inspect.isclass(v) and issubclass(v, BaseException)}


def current_exc_packed():
    exc_class, exc, exc_tb = sys.exc_info()
    if exc_class in builtin_exceptions:
        return {
            "class": builtin_exceptions[exc_class],
            "message": str(exc),
            "traceback": traceback.format_tb(exc_tb)
        }
    else:
        message = traceback.format_exception_only(exc_class, exc)[0].rstrip()
        return {
            "class": "GenericRemoteException",
            "message": message,
            "traceback": traceback.format_tb(exc_tb)
        }


def raise_packed_exc(pack):
    if pack["class"] == "GenericRemoteException":
        cls = GenericRemoteException
    else:
        cls = getattr(builtins, pack["class"])
    exc = cls(pack["message"])
    exc.parent_traceback = pack["traceback"]
    raise exc
