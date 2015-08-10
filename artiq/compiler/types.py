"""
The :mod:`types` module contains the classes describing the types
in :mod:`asttyped`.
"""

import string
from collections import OrderedDict


class UnificationError(Exception):
    def __init__(self, typea, typeb):
        self.typea, self.typeb = typea, typeb


def genalnum():
    ident = ["a"]
    while True:
        yield "".join(ident)
        pos = len(ident) - 1
        while pos >= 0:
            cur_n = string.ascii_lowercase.index(ident[pos])
            if cur_n < 25:
                ident[pos] = string.ascii_lowercase[cur_n + 1]
                break
            else:
                ident[pos] = "a"
                pos -= 1
        if pos < 0:
            ident = ["a"] + ident

def _freeze(dict_):
    return tuple((key, dict_[key]) for key in dict_)

def _map_find(elts):
    if isinstance(elts, list):
        return [x.find() for x in elts]
    elif isinstance(elts, dict):
        return {k: elts[k].find() for k in elts}
    else:
        assert False


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

    def fold(self, accum, fn):
        if self.parent is self:
            return fn(accum, self)
        else:
            return self.find().fold(accum, fn)

    def __repr__(self):
        if self.parent is self:
            return "<py2llvm.types.TVar %d>" % id(self)
        else:
            return repr(self.find())

    # __eq__ and __hash__ are not overridden and default to
    # comparison by identity. Use .find() explicitly before
    # any lookups or comparisons.

class TMono(Type):
    """
    A monomorphic type, possibly parametric.

    :class:`TMono` is supposed to be subclassed by builtin types,
    unlike all other :class:`Type` descendants. Similarly,
    instances of :class:`TMono` should never be allocated directly,
    as that will break the type-sniffing code in :mod:`builtins`.
    """

    attributes = OrderedDict()

    def __init__(self, name, params={}):
        assert isinstance(params, dict)
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

    def fold(self, accum, fn):
        for param in self.params:
            accum = self.params[param].fold(accum, fn)
        return fn(accum, self)

    def __repr__(self):
        return "py2llvm.types.TMono(%s, %s)" % (repr(self.name), repr(self.params))

    def __getitem__(self, param):
        return self.params[param]

    def __eq__(self, other):
        return isinstance(other, TMono) and \
                self.name == other.name and \
                _map_find(self.params) == _map_find(other.params)

    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        return hash((self.name, _freeze(self.params)))

class TTuple(Type):
    """
    A tuple type.

    :ivar elts: (list of :class:`Type`) elements
    """

    attributes = OrderedDict()

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

    def fold(self, accum, fn):
        for elt in self.elts:
            accum = elt.fold(accum, fn)
        return fn(accum, self)

    def __repr__(self):
        return "py2llvm.types.TTuple(%s)" % repr(self.elts)

    def __eq__(self, other):
        return isinstance(other, TTuple) and \
                _map_find(self.elts) == _map_find(other.elts)

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

    attributes = OrderedDict()

    def __init__(self, args, optargs, ret):
        assert isinstance(args, OrderedDict)
        assert isinstance(optargs, OrderedDict)
        assert isinstance(ret, Type)
        self.args, self.optargs, self.ret = args, optargs, ret

    def arity(self):
        return len(self.args) + len(self.optargs)

    def find(self):
        return self

    def unify(self, other):
        if isinstance(other, TFunction) and \
                self.args.keys() == other.args.keys() and \
                self.optargs.keys() == other.optargs.keys():
            for selfarg, otherarg in zip(list(self.args.values()) + list(self.optargs.values()),
                                         list(other.args.values()) + list(other.optargs.values())):
                selfarg.unify(otherarg)
            self.ret.unify(other.ret)
        elif isinstance(other, TVar):
            other.unify(self)
        else:
            raise UnificationError(self, other)

    def fold(self, accum, fn):
        for arg in self.args:
            accum = self.args[arg].fold(accum, fn)
        for optarg in self.optargs:
            accum = self.optargs[optarg].fold(accum, fn)
        accum = self.ret.fold(accum, fn)
        return fn(accum, self)

    def __repr__(self):
        return "py2llvm.types.TFunction({}, {}, {})".format(
            repr(self.args), repr(self.optargs), repr(self.ret))

    def __eq__(self, other):
        return isinstance(other, TFunction) and \
                _map_find(self.args) == _map_find(other.args) and \
                _map_find(self.optargs) == _map_find(other.optargs)

    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        return hash((_freeze(self.args), _freeze(self.optargs), self.ret))

class TRPCFunction(TFunction):
    """
    A function type of a remote function.

    :ivar service: (int) RPC service number
    """

    def __init__(self, args, optargs, ret, service):
        super().__init__(args, optargs, ret)
        self.service = service

    def unify(self, other):
        if isinstance(other, TRPCFunction) and \
                self.service == other.service:
            super().unify(other)
        elif isinstance(other, TVar):
            other.unify(self)
        else:
            raise UnificationError(self, other)

class TCFunction(TFunction):
    """
    A function type of a runtime-provided C function.

    :ivar name: (str) C function name
    """

    def __init__(self, args, ret, name):
        super().__init__(args, OrderedDict(), ret)
        self.name = name

    def unify(self, other):
        if isinstance(other, TCFunction) and \
                self.name == other.name:
            super().unify(other)
        elif isinstance(other, TVar):
            other.unify(self)
        else:
            raise UnificationError(self, other)

class TBuiltin(Type):
    """
    An instance of builtin type. Every instance of a builtin
    type is treated specially according to its name.
    """

    def __init__(self, name):
        assert isinstance(name, str)
        self.name = name
        self.attributes = OrderedDict()

    def find(self):
        return self

    def unify(self, other):
        if self != other:
            raise UnificationError(self, other)

    def fold(self, accum, fn):
        return fn(accum, self)

    def __repr__(self):
        return "py2llvm.types.TBuiltin(%s)" % repr(self.name)

    def __eq__(self, other):
        return isinstance(other, TBuiltin) and \
                self.name == other.name

    def __ne__(self, other):
        return not (self == other)

class TBuiltinFunction(TBuiltin):
    """
    A type of a builtin function.
    """

class TConstructor(TBuiltin):
    """
    A type of a constructor of a builtin class, e.g. ``list``.
    Note that this is not the same as the type of an instance of
    the class, which is ``TMono("list", ...)``.
    """

class TExceptionConstructor(TBuiltin):
    """
    A type of a constructor of a builtin exception, e.g. ``Exception``.
    Note that this is not the same as the type of an instance of
    the class, which is ``TMono("Exception", ...)``.
    """

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

    def fold(self, accum, fn):
        return fn(accum, self)

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
        if param not in typ.params:
            return False
        params_match = params_match and \
            typ.params[param].find() == params[param].find()
    return isinstance(typ, TMono) and \
        (name is None or (typ.name == name and params_match))

def is_polymorphic(typ):
    return typ.fold(False, lambda accum, typ: accum or is_var(typ))

def is_tuple(typ, elts=None):
    typ = typ.find()
    if elts:
        return isinstance(typ, TTuple) and \
            elts == typ.elts
    else:
        return isinstance(typ, TTuple)

def is_function(typ):
    return isinstance(typ.find(), TFunction)

def is_rpc_function(typ):
    return isinstance(typ.find(), TRPCFunction)

def is_c_function(typ):
    return isinstance(typ.find(), TCFunction)

def is_builtin(typ, name=None):
    typ = typ.find()
    if name is None:
        return isinstance(typ, TBuiltin)
    else:
        return isinstance(typ, TBuiltin) and \
            typ.name == name

def is_exn_constructor(typ, name=None):
    typ = typ.find()
    if name is not None:
        return isinstance(typ, TExceptionConstructor) and \
            typ.name == name
    else:
        return isinstance(typ, TExceptionConstructor)

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
        elif isinstance(typ, (TFunction, TRPCFunction, TCFunction)):
            args = []
            args += [ "%s:%s" % (arg, self.name(typ.args[arg]))    for arg in typ.args]
            args += ["?%s:%s" % (arg, self.name(typ.optargs[arg])) for arg in typ.optargs]
            signature = "(%s)->%s" % (", ".join(args), self.name(typ.ret))

            if isinstance(typ, TRPCFunction):
                return "rpc({}) {}".format(typ.service, signature)
            if isinstance(typ, TCFunction):
                return "ffi({}) {}".format(repr(typ.name), signature)
            elif isinstance(typ, TFunction):
                return signature
        elif isinstance(typ, TBuiltinFunction):
            return "<function %s>" % typ.name
        elif isinstance(typ, (TConstructor, TExceptionConstructor)):
            return "<constructor %s>" % typ.name
        elif isinstance(typ, TValue):
            return repr(typ.value)
        else:
            assert False
