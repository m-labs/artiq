"""
Values representing ARTIQ types, to be used in function type
annotations.
"""

from artiq.compiler import types, builtins

__all__ = ["TNone", "TTuple",
           "TBool", "TInt32", "TInt64", "TFloat",
           "TStr", "TBytes", "TByteArray",
           "TList", "TRange32", "TRange64",
           "TVar"]

TNone      = builtins.TNone()
TBool      = builtins.TBool()
TInt32     = builtins.TInt(types.TValue(32))
TInt64     = builtins.TInt(types.TValue(64))
TFloat     = builtins.TFloat()
TStr       = builtins.TStr()
TBytes     = builtins.TBytes()
TByteArray = builtins.TByteArray()
TTuple     = types.TTuple
TList      = builtins.TList
TRange32   = builtins.TRange(builtins.TInt(types.TValue(32)))
TRange64   = builtins.TRange(builtins.TInt(types.TValue(64)))
TVar       = types.TVar
