"""
The :mod:`builtins` module contains the builtin Python and ARTIQ
types, such as int or float.
"""

from . import types

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

class TTuple(types.Type):
    """A tuple type."""

    attributes = {}

    def __init__(self, elts=[]):
        self.elts = elts

    def find(self):
        return self

    def unify(self, other):
        if isinstance(other, TTuple) and len(self.elts) == len(other.elts):
            for selfelt, otherelt in zip(self.elts, other.elts):
                selfelt.unify(otherelt)
        elif isinstance(other, TVar):
            other.unify(self)
        else:
            raise UnificationError(self, other)

    def __repr__(self):
        return "TTuple(%s)" % (", ".join(map(repr, self.elts)))

    def __eq__(self, other):
        return isinstance(other, TTuple) and \
                self.elts == other.elts

    def __ne__(self, other):
        return not (self == other)

class TList(types.TMono):
    def __init__(self, elt=None):
        if elt is None:
            elt = types.TVar()
        super().__init__("list", {"elt": elt})


def is_int(typ, width=None):
    if width:
        return types.is_mono(typ, "int", {"width": width})
    else:
        return types.is_mono(typ, "int")

def is_numeric(typ):
    return isinstance(typ, types.TMono) and \
        typ.name in ('int', 'float')
