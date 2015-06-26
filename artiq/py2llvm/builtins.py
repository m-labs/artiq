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

def fn_bool():
    return types.TBuiltin("class bool")

def fn_int():
    return types.TBuiltin("class int")

def fn_float():
    return types.TBuiltin("class float")

def fn_list():
    return types.TBuiltin("class list")

def fn_len():
    return types.TBuiltin("function len")

def fn_round():
    return types.TBuiltin("function round")

def fn_range():
    return types.TBuiltin("function range")

def fn_syscall():
    return types.TBuiltin("function syscall")

# Accessors

def is_none(typ):
    return types.is_mono(typ, "NoneType")

def is_bool(typ):
    return types.is_mono(typ, "bool")

def is_int(typ, width=None):
    if width:
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
    if elt:
        return types.is_mono(typ, "list", {"elt": elt})
    else:
        return types.is_mono(typ, "list")

def is_collection(typ):
    typ = typ.find()
    return isinstance(typ, types.TTuple) or \
        types.is_mono(typ, "list")

def is_builtin(typ, name):
    typ = typ.find()
    return isinstance(typ, types.TBuiltin) and \
        typ.name == name
