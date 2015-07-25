"""
The :mod:`builtins` module contains the builtin Python
and ARTIQ types, such as int or float.
"""

from collections import OrderedDict
from . import types

# Types

class TNone(types.TMono):
    def __init__(self):
        super().__init__("NoneType")

class TBool(types.TMono):
    def __init__(self):
        super().__init__("bool")

    @staticmethod
    def zero():
        return False

    @staticmethod
    def one():
        return True

class TInt(types.TMono):
    def __init__(self, width=None):
        if width is None:
            width = types.TVar()
        super().__init__("int", {"width": width})

    @staticmethod
    def zero():
        return 0

    @staticmethod
    def one():
        return 1

class TFloat(types.TMono):
    def __init__(self):
        super().__init__("float")

    @staticmethod
    def zero():
        return 0.0

    @staticmethod
    def one():
        return 1.0

class TStr(types.TMono):
    def __init__(self):
        super().__init__("str")

class TList(types.TMono):
    def __init__(self, elt=None):
        if elt is None:
            elt = types.TVar()
        super().__init__("list", {"elt": elt})

class TRange(types.TMono):
    def __init__(self, elt=None):
        if elt is None:
            elt = types.TVar()
        super().__init__("range", {"elt": elt})
        self.attributes = OrderedDict([
            ("start", elt),
            ("stop",  elt),
            ("step",  elt),
        ])

class TException(types.TMono):
    # All exceptions share the same internal layout:
    #  * Pointer to the unique global with the name of the exception (str)
    #    (which also serves as the EHABI type_info).
    #  * File, line and column where it was raised (str, int, int).
    #  * Message, which can contain substitutions {0}, {1} and {2} (str).
    #  * Three 64-bit integers, parameterizing the message (int(width=64)).


    # Keep this in sync with the function ARTIQIRGenerator.alloc_exn.
    attributes = OrderedDict([
        ("__name__",    TStr()),
        ("__file__",    TStr()),
        ("__line__",    TInt(types.TValue(32))),
        ("__col__",     TInt(types.TValue(32))),
        ("__message__", TStr()),
        ("__param0__",  TInt(types.TValue(64))),
        ("__param1__",  TInt(types.TValue(64))),
        ("__param2__",  TInt(types.TValue(64))),
    ])

    def __init__(self, name="Exception"):
        super().__init__(name)

class TIndexError(TException):
    def __init__(self):
        super().__init__("IndexError")

class TValueError(TException):
    def __init__(self):
        super().__init__("ValueError")

class TZeroDivisionError(TException):
    def __init__(self):
        super().__init__("ZeroDivisionError")

def fn_bool():
    return types.TConstructor("bool")

def fn_int():
    return types.TConstructor("int")

def fn_float():
    return types.TConstructor("float")

def fn_str():
    return types.TConstructor("str")

def fn_list():
    return types.TConstructor("list")

def fn_Exception():
    return types.TExceptionConstructor("Exception")

def fn_IndexError():
    return types.TExceptionConstructor("IndexError")

def fn_ValueError():
    return types.TExceptionConstructor("ValueError")

def fn_ZeroDivisionError():
    return types.TExceptionConstructor("ZeroDivisionError")

def fn_range():
    return types.TBuiltinFunction("range")

def fn_len():
    return types.TBuiltinFunction("len")

def fn_round():
    return types.TBuiltinFunction("round")

def fn_print():
    return types.TBuiltinFunction("print")

def fn_syscall():
    return types.TBuiltinFunction("syscall")

# Accessors

def is_none(typ):
    return types.is_mono(typ, "NoneType")

def is_bool(typ):
    return types.is_mono(typ, "bool")

def is_int(typ, width=None):
    if width is not None:
        return types.is_mono(typ, "int", {"width": width})
    else:
        return types.is_mono(typ, "int")

def get_int_width(typ):
    if is_int(typ):
        return types.get_value(typ.find()["width"])

def is_float(typ):
    return types.is_mono(typ, "float")

def is_str(typ):
    return types.is_mono(typ, "str")

def is_numeric(typ):
    typ = typ.find()
    return isinstance(typ, types.TMono) and \
        typ.name in ('int', 'float')

def is_list(typ, elt=None):
    if elt is not None:
        return types.is_mono(typ, "list", {"elt": elt})
    else:
        return types.is_mono(typ, "list")

def is_range(typ, elt=None):
    if elt is not None:
        return types.is_mono(typ, "range", {"elt": elt})
    else:
        return types.is_mono(typ, "range")

def is_exception(typ, name=None):
    if name is None:
        return isinstance(typ.find(), TException)
    else:
        return isinstance(typ.find(), TException) and \
            typ.name == name

def is_iterable(typ):
    typ = typ.find()
    return isinstance(typ, types.TMono) and \
        typ.name in ('list', 'range')

def get_iterable_elt(typ):
    if is_iterable(typ):
        return typ.find()["elt"].find()

def is_collection(typ):
    typ = typ.find()
    return isinstance(typ, types.TTuple) or \
        types.is_mono(typ, "list")

def is_allocated(typ):
    return typ.fold(False, lambda accum, typ:
        is_list(typ) or is_str(typ) or types.is_function(typ) or
        is_exception(typ))
