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
            return "<py2llvm.types.TVar %d>" % id(self)
        else:
            return repr(self.find())

    # __eq__ and __hash__ are not overridden and default to
    # comparison by identity. Use .find() explicitly before
    # any lookups or comparisons.

class TMono(Type):
    """A monomorphic type, possibly parametric."""

    attributes = {}

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
        return "py2llvm.types.TMono(%s, %s)" % (repr(self.name), repr(self.params))

    def __getitem__(self, param):
        return self.params[param]

    def __eq__(self, other):
        return isinstance(other, TMono) and \
                self.name == other.name and \
                self.params == other.params

    def __ne__(self, other):
        return not (self == other)

class TTuple(Type):
    """
    A tuple type.

    :ivar elts: (list of :class:`Type`) elements
    """

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
        return "py2llvm.types.TTuple(%s)" % repr(self.elts)

    def __eq__(self, other):
        return isinstance(other, TTuple) and \
                self.elts == other.elts

    def __ne__(self, other):
        return not (self == other)

class TFunction(Type):
    """
    A function type.

    :ivar args: (:class:`collections.OrderedDict` of string to :class:`Type`)
        mandatory arguments
    :ivar optargs: (:class:`collections.OrderedDict` of string to :class:`Type`)
        optional arguments
    :ivar ret: (:class:`Type`)
        return type
    """

    attributes = {}

    def __init__(self, args, optargs, ret):
        self.args, self.optargs, self.ret = args, optargs, ret

    def arity(self):
        return len(self.args) + len(self.optargs)

    def find(self):
        return self

    def unify(self, other):
        if isinstance(other, TFunction) and \
                self.args.keys() == other.args.keys() and \
                self.optargs.keys() == other.optargs.keys():
            for selfarg, otherarg in zip(self.args.values() + self.optargs.values(),
                                         other.args.values() + other.optargs.values()):
                selfarg.unify(otherarg)
            self.ret.unify(other.ret)
        elif isinstance(other, TVar):
            other.unify(self)
        else:
            raise UnificationError(self, other)

    def __repr__(self):
        return "py2llvm.types.TFunction(%s, %s, %s)" % \
            (repr(self.args), repr(self.optargs), repr(self.ret))

    def __eq__(self, other):
        return isinstance(other, TFunction) and \
                self.args == other.args and \
                self.optargs == other.optargs

    def __ne__(self, other):
        return not (self == other)

class TBuiltin(Type):
    """
    An instance of builtin type. Every instance of a builtin
    type is treated specially according to its name.
    """

    def __init__(self, name):
        self.name = name

    def find(self):
        return self

    def unify(self, other):
        if self != other:
            raise UnificationError(self, other)

    def __repr__(self):
        return "py2llvm.types.TBuiltin(%s)" % repr(self.name)

    def __eq__(self, other):
        return isinstance(other, TBuiltin) and \
                self.name == other.name

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
        return "py2llvm.types.TValue(%s)" % repr(self.value)

    def __eq__(self, other):
        return isinstance(other, TValue) and \
                self.value == other.value

    def __ne__(self, other):
        return not (self == other)


def is_var(typ):
    return isinstance(typ.find(), TVar)

def is_mono(typ, name=None, **params):
    typ = typ.find()
    params_match = True
    for param in params:
        params_match = params_match and \
            typ.params[param].find() == params[param].find()
    return isinstance(typ, TMono) and \
        (name is None or (typ.name == name and params_match))

def is_tuple(typ, elts=None):
    typ = typ.find()
    if elts:
        return isinstance(typ, TTuple) and \
            elts == typ.elts
    else:
        return isinstance(typ, TTuple)

def is_function(typ):
    return isinstance(typ.find(), TFunction)

def is_builtin(typ):
    return isinstance(typ.find(), TBuiltin)

def get_value(typ):
    typ = typ.find()
    if isinstance(typ, TVar):
        return None
    elif isinstance(typ, TValue):
        return typ.value
    else:
        assert False

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
        elif isinstance(typ, TFunction):
            args = []
            args += [ "%s:%s" % (arg, self.name(typ.args[arg]))    for arg in typ.args]
            args += ["?%s:%s" % (arg, self.name(typ.optargs[arg])) for arg in typ.optargs]
            return "(%s)->%s" % (", ".join(args), self.name(typ.ret))
        elif isinstance(typ, TBuiltin):
            return "<built-in %s>" % typ.name
        elif isinstance(typ, TValue):
            return repr(typ.value)
        else:
            assert False
