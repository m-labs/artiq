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

def TInt32():
    return TInt(types.TValue(32))

def TInt64():
    return TInt(types.TValue(64))

def _int_printer(typ, printer, depth, max_depth):
    if types.is_var(typ["width"]):
        return "numpy.int?"
    else:
        return "numpy.int{}".format(types.get_value(typ.find()["width"]))
types.TypePrinter.custom_printers["int"] = _int_printer

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

class TBytes(types.TMono):
    def __init__(self):
        super().__init__("bytes")

class TByteArray(types.TMono):
    def __init__(self):
        super().__init__("bytearray")

class TList(types.TMono):
    def __init__(self, elt=None):
        if elt is None:
            elt = types.TVar()
        super().__init__("list", {"elt": elt})

class TArray(types.TMono):
    def __init__(self, elt=None):
        if elt is None:
            elt = types.TVar()
        super().__init__("array", {"elt": elt})

def _array_printer(typ, printer, depth, max_depth):
    return "numpy.array(elt={})".format(printer.name(typ["elt"], depth, max_depth))
types.TypePrinter.custom_printers["array"] = _array_printer

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
    #  * Three 64-bit integers, parameterizing the message (numpy.int64).

    # Keep this in sync with the function ARTIQIRGenerator.alloc_exn.
    attributes = OrderedDict([
        ("__name__",    TStr()),
        ("__file__",    TStr()),
        ("__line__",    TInt32()),
        ("__col__",     TInt32()),
        ("__func__",    TStr()),
        ("__message__", TStr()),
        ("__param0__",  TInt64()),
        ("__param1__",  TInt64()),
        ("__param2__",  TInt64()),
    ])

    def __init__(self, name="Exception", id=0):
        super().__init__(name)
        self.id = id

def fn_bool():
    return types.TConstructor(TBool())

def fn_int():
    return types.TConstructor(TInt())

def fn_int32():
    return types.TBuiltinFunction("int32")

def fn_int64():
    return types.TBuiltinFunction("int64")

def fn_float():
    return types.TConstructor(TFloat())

def fn_str():
    return types.TConstructor(TStr())

def fn_bytes():
    return types.TConstructor(TBytes())

def fn_bytearray():
    return types.TConstructor(TByteArray())

def fn_list():
    return types.TConstructor(TList())

def fn_array():
    return types.TConstructor(TArray())

def fn_Exception():
    return types.TExceptionConstructor(TException("Exception"))

def fn_IndexError():
    return types.TExceptionConstructor(TException("IndexError"))

def fn_ValueError():
    return types.TExceptionConstructor(TException("ValueError"))

def fn_ZeroDivisionError():
    return types.TExceptionConstructor(TException("ZeroDivisionError"))

def fn_RuntimeError():
    return types.TExceptionConstructor(TException("RuntimeError"))

def fn_range():
    return types.TBuiltinFunction("range")

def fn_len():
    return types.TBuiltinFunction("len")

def fn_round():
    return types.TBuiltinFunction("round")

def fn_abs():
    return types.TBuiltinFunction("abs")

def fn_min():
    return types.TBuiltinFunction("min")

def fn_max():
    return types.TBuiltinFunction("max")

def fn_make_array():
    return types.TBuiltinFunction("make_array")

def fn_print():
    return types.TBuiltinFunction("print")

def fn_kernel():
    return types.TBuiltinFunction("kernel")

def obj_parallel():
    return types.TBuiltin("parallel")

def obj_interleave():
    return types.TBuiltin("interleave")

def obj_sequential():
    return types.TBuiltin("sequential")

def fn_watchdog():
    return types.TBuiltinFunction("watchdog")

def fn_delay():
    return types.TBuiltinFunction("delay")

def fn_now_mu():
    return types.TBuiltinFunction("now_mu")

def fn_delay_mu():
    return types.TBuiltinFunction("delay_mu")

def fn_at_mu():
    return types.TBuiltinFunction("at_mu")

def fn_rtio_log():
    return types.TBuiltinFunction("rtio_log")

# Accessors

def is_none(typ):
    return types.is_mono(typ, "NoneType")

def is_bool(typ):
    return types.is_mono(typ, "bool")

def is_int(typ, width=None):
    if width is not None:
        return types.is_mono(typ, "int", width=width)
    else:
        return types.is_mono(typ, "int")

def is_int32(typ):
    return is_int(typ, types.TValue(32))

def is_int64(typ):
    return is_int(typ, types.TValue(64))

def get_int_width(typ):
    if is_int(typ):
        return types.get_value(typ.find()["width"])

def is_float(typ):
    return types.is_mono(typ, "float")

def is_str(typ):
    return types.is_mono(typ, "str")

def is_bytes(typ):
    return types.is_mono(typ, "bytes")

def is_bytearray(typ):
    return types.is_mono(typ, "bytearray")

def is_numeric(typ):
    typ = typ.find()
    return isinstance(typ, types.TMono) and \
        typ.name in ('int', 'float')

def is_list(typ, elt=None):
    if elt is not None:
        return types.is_mono(typ, "list", elt=elt)
    else:
        return types.is_mono(typ, "list")

def is_array(typ, elt=None):
    if elt is not None:
        return types.is_mono(typ, "array", elt=elt)
    else:
        return types.is_mono(typ, "array")

def is_listish(typ, elt=None):
    if is_list(typ, elt) or is_array(typ, elt):
        return True
    elif elt is None:
        return is_str(typ) or is_bytes(typ) or is_bytearray(typ)
    else:
        return False

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
    return is_listish(typ) or is_range(typ)

def get_iterable_elt(typ):
    if is_str(typ) or is_bytes(typ) or is_bytearray(typ):
        return TInt(types.TValue(8))
    elif is_iterable(typ):
        return typ.find()["elt"].find()
    else:
        assert False

def is_collection(typ):
    typ = typ.find()
    return isinstance(typ, types.TTuple) or \
        types.is_mono(typ, "list")

def is_allocated(typ):
    return not (is_none(typ) or is_bool(typ) or is_int(typ) or
                  is_float(typ) or is_range(typ) or
                  types._is_pointer(typ) or types.is_function(typ) or
                  types.is_c_function(typ) or types.is_rpc(typ) or
                  types.is_method(typ) or types.is_tuple(typ) or
                  types.is_value(typ))
