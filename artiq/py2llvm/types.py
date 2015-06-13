"""
The :mod:`types` module contains the classes describing the types
in :mod:`asttyped`.
"""

import string

def genalnum():
    ident = ["a"]
    while True:
        yield "".join(ident)
        pos = len(ident) - 1
        while pos >= 0:
            cur_n = string.ascii_lowercase.index(ident[pos])
            if cur_n < 26:
                ident[pos] = string.ascii_lowercase[cur_n + 1]
                break
            else:
                ident[pos] = "a"
                pos -= 1
        if pos < 0:
            ident = "a" + ident

class UnificationError(Exception):
    def __init__(self, typea, typeb):
        self.typea, self.typeb = typea, typeb


class Type(object):
    pass

class TVar(Type):
    """
    A type variable.

    In effect, the classic union-find data structure is intrusively
    folded into this class.
    """

    attributes = ()

    def __init__(self):
        self.parent = self

    def find(self):
        if self.parent is self:
            return self
        else:
            root = self.parent.find()
            self.parent = root # path compression
            return root

    def unify(self, other):
        other = other.find()

        if self.parent is self:
            self.parent = other
        else:
            self.find().unify(other)

    def __repr__(self):
        if self.parent is self:
            return "TVar(%d)" % id(self)
        else:
            return repr(self.find())

    # __eq__ and __hash__ are not overridden and default to
    # comparison by identity. Use .find() explicitly before
    # any lookups or comparisons.

class TMono(Type):
    """A monomorphic type, possibly parametric."""

    def __init__(self, name, params={}):
        self.name, self.params = name, params

    def find(self):
        return self

    def unify(self, other):
        if isinstance(other, TMono) and self.name == other.name:
            assert self.params.keys() == other.params.keys()
            for param in self.params:
                self.params[param].unify(other.params[param])
        elif isinstance(other, TVar):
            other.unify(self)
        else:
            raise UnificationError(self, other)

    def __repr__(self):
        return "TMono(%s, %s)" % (repr(self.name), repr(self.params))

    def __getitem__(self, param):
        return self.params[param]

    def __eq__(self, other):
        return isinstance(other, TMono) and \
                self.name == other.name and \
                self.params == other.params

    def __ne__(self, other):
        return not (self == other)

class TValue(Type):
    """
    A type-level value (such as the integer denoting width of
    a generic integer type.
    """

    def __init__(self, value):
        self.value = value

    def find(self):
        return self

    def unify(self, other):
        if isinstance(other, TVar):
            other.unify(self)
        elif self != other:
            raise UnificationError(self, other)

    def __repr__(self):
        return "TValue(%s)" % repr(self.value)

    def __eq__(self, other):
        return isinstance(other, TValue) and \
                self.value == other.value

    def __ne__(self, other):
        return not (self == other)


def is_var(typ):
    return isinstance(typ, TVar)

def is_mono(typ, name, **params):
    params_match = True
    for param in params:
        params_match = params_match and typ.params[param] == params[param]
    return isinstance(typ, TMono) and \
        typ.name == name and params_match


class TypePrinter(object):
    """
    A class that prints types using Python-like syntax and gives
    type variables sequential alphabetic names.
    """

    def __init__(self):
        self.gen = genalnum()
        self.map = {}

    def name(self, typ):
        typ = typ.find()
        if isinstance(typ, TVar):
            if typ not in self.map:
                self.map[typ] = "'%s" % next(self.gen)
            return self.map[typ]
        elif isinstance(typ, TMono):
            if typ.params == {}:
                return typ.name
            else:
                return "%s(%s)" % (typ.name, ", ".join(
                    ["%s=%s" % (k, self.name(typ.params[k])) for k in typ.params]))
        elif isinstance(typ, TTuple):
            if len(typ.elts) == 1:
                return "(%s,)" % self.name(typ.elts[0])
            else:
                return "(%s)" % ", ".join(list(map(self.name, typ.elts)))
        elif isinstance(typ, TValue):
            return repr(typ.value)
        else:
            assert False
