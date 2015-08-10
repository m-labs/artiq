"""
Values representing ARTIQ types, to be used in function type
annotations.
"""

from artiq.compiler import types, builtins

__all__ = ["TNone", "TBool", "TInt32", "TInt64", "TFloat",
           "TStr", "TList", "TRange32", "TRange64"]

TNone      = builtins.TNone()
TBool      = builtins.TBool()
TInt32     = builtins.TInt(types.TValue(32))
TInt64     = builtins.TInt(types.TValue(64))
TFloat     = builtins.TFloat()
TStr       = builtins.TStr()
TList      = builtins.TList
TRange32   = builtins.TRange(builtins.TInt(types.TValue(32)))
TRange64   = builtins.TRange(builtins.TInt(types.TValue(64)))
