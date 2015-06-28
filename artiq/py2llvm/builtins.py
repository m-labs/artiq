"""
The :mod:`builtins` module contains the builtin Python
and ARTIQ types, such as int or float.
"""

from . import types

# Types

class TNone(types.TMono):
    def __init__(self):
        super().__init__("NoneType")

class TBool(types.TMono):
    def __init__(self):
        super().__init__("bool")

class TInt(types.TMono):
    def __init__(self, width=None):
        if width is None:
            width = types.TVar()
        super().__init__("int", {"width": width})

class TFloat(types.TMono):
    def __init__(self):
        super().__init__("float")

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

class TException(types.TMono):
    def __init__(self):
        super().__init__("Exception")

def fn_bool():
    return types.TConstructor("bool")

def fn_int():
    return types.TConstructor("int")

def fn_float():
    return types.TConstructor("float")

def fn_list():
    return types.TConstructor("list")

def fn_Exception():
    return types.TExceptionConstructor("Exception")

def fn_range():
    return types.TBuiltinFunction("range")

def fn_len():
    return types.TBuiltinFunction("len")

def fn_round():
    return types.TBuiltinFunction("round")

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

def is_iterable(typ):
    typ = typ.find()
    return isinstance(typ, types.TMono) and \
        typ.name in ('list', 'range')

def get_iterable_elt(typ):
    if is_iterable(typ):
        return typ.find()["elt"]

def is_collection(typ):
    typ = typ.find()
    return isinstance(typ, types.TTuple) or \
        types.is_mono(typ, "list")

def is_builtin(typ, name):
    typ = typ.find()
    return isinstance(typ, types.TBuiltin) and \
        typ.name == name

def is_exception(typ, name=None):
    typ = typ.find()
    if name is not None:
        return isinstance(typ, types.TExceptionConstructor) and \
            typ.name == name
    else:
        return isinstance(typ, types.TExceptionConstructor)
