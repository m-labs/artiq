"""
The :mod:`types` module contains the classes describing the types
in :mod:`asttyped`.
"""

import string
from collections import OrderedDict
from . import iodelay


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
    def __str__(self):
        return TypePrinter().name(self)

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
            # The recursive find() invocation is turned into a loop
            # because paths resulting from unification of large arrays
            # can easily cause a stack overflow.
            root = self
            while root.__class__ == TVar:
                if root is root.parent:
                    break
                else:
                    root = root.parent

            # path compression
            iter = self
            while iter.__class__ == TVar:
                if iter is root:
                    break
                else:
                    iter, iter.parent = iter.parent, root

            return root

    def unify(self, other):
        if other is self:
            return
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
            return "<artiq.compiler.types.TVar %d>" % id(self)
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
        assert isinstance(params, (dict, OrderedDict))
        self.name, self.params = name, OrderedDict(sorted(params.items()))

    def find(self):
        return self

    def unify(self, other):
        if other is self:
            return
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
        return "artiq.compiler.types.TMono(%s, %s)" % (repr(self.name), repr(self.params))

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
        if other is self:
            return
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
        return "artiq.compiler.types.TTuple(%s)" % repr(self.elts)

    def __eq__(self, other):
        return isinstance(other, TTuple) and \
                _map_find(self.elts) == _map_find(other.elts)

    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        return hash(tuple(self.elts))

class _TPointer(TMono):
    def __init__(self):
        super().__init__("pointer")

class TFunction(Type):
    """
    A function type.

    :ivar args: (:class:`collections.OrderedDict` of string to :class:`Type`)
        mandatory arguments
    :ivar optargs: (:class:`collections.OrderedDict` of string to :class:`Type`)
        optional arguments
    :ivar ret: (:class:`Type`)
        return type
    :ivar delay: (:class:`Type`)
        RTIO delay
    """

    attributes = OrderedDict([
        ('__closure__', _TPointer()),
        ('__code__',    _TPointer()),
    ])

    def __init__(self, args, optargs, ret):
        assert isinstance(args, OrderedDict)
        assert isinstance(optargs, OrderedDict)
        assert isinstance(ret, Type)
        self.args, self.optargs, self.ret = args, optargs, ret
        self.delay = TVar()

    def arity(self):
        return len(self.args) + len(self.optargs)

    def arg_names(self):
        return list(self.args.keys()) + list(self.optargs.keys())

    def find(self):
        return self

    def unify(self, other):
        if other is self:
            return
        if isinstance(other, TFunction) and \
                self.args.keys() == other.args.keys() and \
                self.optargs.keys() == other.optargs.keys():
            for selfarg, otherarg in zip(list(self.args.values()) + list(self.optargs.values()),
                                         list(other.args.values()) + list(other.optargs.values())):
                selfarg.unify(otherarg)
            self.ret.unify(other.ret)
            self.delay.unify(other.delay)
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
        return "artiq.compiler.types.TFunction({}, {}, {})".format(
            repr(self.args), repr(self.optargs), repr(self.ret))

    def __eq__(self, other):
        return isinstance(other, TFunction) and \
                _map_find(self.args) == _map_find(other.args) and \
                _map_find(self.optargs) == _map_find(other.optargs)

    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        return hash((_freeze(self.args), _freeze(self.optargs), self.ret))

class TCFunction(TFunction):
    """
    A function type of a runtime-provided C function.

    :ivar name: (str) C function name
    :ivar flags: (set of str) C function flags.
        Flag ``nounwind`` means the function never raises an exception.
        Flag ``nowrite`` means the function never writes any memory
        that the ARTIQ Python code can observe.
    """

    attributes = OrderedDict()

    def __init__(self, args, ret, name, flags={}):
        assert isinstance(flags, set)
        for flag in flags:
            assert flag in {'nounwind', 'nowrite'}
        super().__init__(args, OrderedDict(), ret)
        self.name  = name
        self.delay = TFixedDelay(iodelay.Const(0))
        self.flags = flags

    def unify(self, other):
        if other is self:
            return
        if isinstance(other, TCFunction) and \
                self.name == other.name:
            super().unify(other)
        elif isinstance(other, TVar):
            other.unify(self)
        else:
            raise UnificationError(self, other)

class TRPC(Type):
    """
    A type of a remote call.

    :ivar ret: (:class:`Type`)
        return type
    :ivar service: (int) RPC service number
    :ivar is_async: (bool) whether the RPC blocks until return
    """

    attributes = OrderedDict()

    def __init__(self, ret, service, is_async=False):
        assert isinstance(ret, Type)
        self.ret, self.service, self.is_async = ret, service, is_async

    def find(self):
        return self

    def unify(self, other):
        if other is self:
            return
        if isinstance(other, TRPC) and \
                self.service == other.service and \
                self.is_async == other.is_async:
            self.ret.unify(other.ret)
        elif isinstance(other, TVar):
            other.unify(self)
        else:
            raise UnificationError(self, other)

    def fold(self, accum, fn):
        accum = self.ret.fold(accum, fn)
        return fn(accum, self)

    def __repr__(self):
        return "artiq.compiler.types.TRPC({})".format(repr(self.ret))

    def __eq__(self, other):
        return isinstance(other, TRPC) and \
                self.service == other.service and \
                self.is_async == other.is_async

    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        return hash(self.service)

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
        if other is self:
            return
        if self != other:
            raise UnificationError(self, other)

    def fold(self, accum, fn):
        return fn(accum, self)

    def __repr__(self):
        return "artiq.compiler.types.{}({})".format(type(self).__name__, repr(self.name))

    def __eq__(self, other):
        return isinstance(other, TBuiltin) and \
                self.name == other.name

    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        return hash(self.name)

class TBuiltinFunction(TBuiltin):
    """
    A type of a builtin function.
    """

class TConstructor(TBuiltin):
    """
    A type of a constructor of a class, e.g. ``list``.
    Note that this is not the same as the type of an instance of
    the class, which is ``TMono("list", ...)`` (or a descendant).

    :ivar instance: (:class:`Type`)
        the type of the instance created by this constructor
    """

    def __init__(self, instance):
        assert isinstance(instance, TMono)
        super().__init__(instance.name)
        self.instance = instance

class TExceptionConstructor(TConstructor):
    """
    A type of a constructor of an exception, e.g. ``Exception``.
    Note that this is not the same as the type of an instance of
    the class, which is ``TMono("Exception", ...)``.
    """

class TInstance(TMono):
    """
    A type of an instance of a user-defined class.

    :ivar constructor: (:class:`TConstructor`)
        the type of the constructor with which this instance
        was created
    """

    def __init__(self, name, attributes):
        assert isinstance(attributes, OrderedDict)
        super().__init__(name)
        self.attributes = attributes
        self.constant_attributes = set()

    def __repr__(self):
        return "artiq.compiler.types.TInstance({}, {})".format(
                    repr(self.name), repr(self.attributes))

class TModule(TMono):
    """
    A type of a module.
    """

    def __init__(self, name, attributes):
        assert isinstance(attributes, OrderedDict)
        super().__init__(name)
        self.attributes = attributes
        self.constant_attributes = set()

    def __repr__(self):
        return "artiq.compiler.types.TModule({}, {})".format(
                    repr(self.name), repr(self.attributes))

class TMethod(TMono):
    """
    A type of a method.
    """

    def __init__(self, self_type, function_type):
        super().__init__("method", {"self": self_type, "fn": function_type})
        self.attributes = OrderedDict([
            ("__func__", function_type),
            ("__self__", self_type),
        ])

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
        if other is self:
            return
        if isinstance(other, TVar):
            other.unify(self)
        elif self != other:
            raise UnificationError(self, other)

    def fold(self, accum, fn):
        return fn(accum, self)

    def __repr__(self):
        return "artiq.compiler.types.TValue(%s)" % repr(self.value)

    def __eq__(self, other):
        return isinstance(other, TValue) and \
                self.value == other.value

    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        return hash(self.value)

class TDelay(Type):
    """
    The type-level representation of IO delay.
    """

    def __init__(self, duration, cause):
        # Avoid pulling in too many dependencies with `artiq.language`.
        from pythonparser import diagnostic
        assert duration is None or isinstance(duration, iodelay.Expr)
        assert cause is None or isinstance(cause, diagnostic.Diagnostic)
        assert (not (duration and cause)) and (duration or cause)
        self.duration, self.cause = duration, cause

    def is_fixed(self):
        return self.duration is not None

    def is_indeterminate(self):
        return self.cause is not None

    def find(self):
        return self

    def unify(self, other):
        other = other.find()

        if isinstance(other, TVar):
            other.unify(self)
        elif self.is_fixed() and other.is_fixed() and \
                self.duration.fold() == other.duration.fold():
            pass
        elif self is not other:
            raise UnificationError(self, other)

    def fold(self, accum, fn):
        # delay types do not participate in folding
        pass

    def __eq__(self, other):
        return isinstance(other, TDelay) and \
                (self.duration == other.duration and \
                 self.cause == other.cause)

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        if self.duration is None:
            return "<{}.TIndeterminateDelay>".format(__name__)
        elif self.cause is None:
            return "{}.TFixedDelay({})".format(__name__, self.duration)
        else:
            assert False

def TIndeterminateDelay(cause):
    return TDelay(None, cause)

def TFixedDelay(duration):
    return TDelay(duration, None)


def is_var(typ):
    return isinstance(typ.find(), TVar)

def is_mono(typ, name=None, **params):
    typ = typ.find()

    if not isinstance(typ, TMono):
        return False

    if name is not None and typ.name != name:
        return False

    for param in params:
        if param not in typ.params:
            return False
        if typ.params[param].find() != params[param].find():
            return False
    return True

def is_polymorphic(typ):
    return typ.fold(False, lambda accum, typ: accum or is_var(typ))

def is_tuple(typ, elts=None):
    typ = typ.find()
    if elts:
        return isinstance(typ, TTuple) and \
            elts == typ.elts
    else:
        return isinstance(typ, TTuple)

def _is_pointer(typ):
    return isinstance(typ.find(), _TPointer)

def is_function(typ):
    return isinstance(typ.find(), TFunction)

def is_rpc(typ):
    return isinstance(typ.find(), TRPC)

def is_c_function(typ, name=None):
    typ = typ.find()
    if name is None:
        return isinstance(typ, TCFunction)
    else:
        return isinstance(typ, TCFunction) and \
            typ.name == name

def is_builtin(typ, name=None):
    typ = typ.find()
    if name is None:
        return isinstance(typ, TBuiltin)
    else:
        return isinstance(typ, TBuiltin) and \
            typ.name == name

def is_builtin_function(typ, name=None):
    typ = typ.find()
    if name is None:
        return isinstance(typ, TBuiltinFunction)
    else:
        return isinstance(typ, TBuiltinFunction) and \
            typ.name == name

def is_constructor(typ, name=None):
    typ = typ.find()
    if name is not None:
        return isinstance(typ, TConstructor) and \
            typ.name == name
    else:
        return isinstance(typ, TConstructor)

def is_exn_constructor(typ, name=None):
    typ = typ.find()
    if name is not None:
        return isinstance(typ, TExceptionConstructor) and \
            typ.name == name
    else:
        return isinstance(typ, TExceptionConstructor)

def is_instance(typ, name=None):
    typ = typ.find()
    if name is not None:
        return isinstance(typ, TInstance) and \
            typ.name == name
    else:
        return isinstance(typ, TInstance)

def is_module(typ, name=None):
    typ = typ.find()
    if name is not None:
        return isinstance(typ, TModule) and \
            typ.name == name
    else:
        return isinstance(typ, TModule)

def is_method(typ):
    return isinstance(typ.find(), TMethod)

def get_method_self(typ):
    if is_method(typ):
        return typ.find().params["self"].find()

def get_method_function(typ):
    if is_method(typ):
        return typ.find().params["fn"].find()

def is_value(typ):
    return isinstance(typ.find(), TValue)

def get_value(typ):
    typ = typ.find()
    if isinstance(typ, TVar):
        return None
    elif isinstance(typ, TValue):
        return typ.value
    else:
        assert False

def is_delay(typ):
    return isinstance(typ.find(), TDelay)

def is_fixed_delay(typ):
    return is_delay(typ) and typ.find().is_fixed()

def is_indeterminate_delay(typ):
    return is_delay(typ) and typ.find().is_indeterminate()


class TypePrinter(object):
    """
    A class that prints types using Python-like syntax and gives
    type variables sequential alphabetic names.
    """

    custom_printers = {}

    def __init__(self):
        self.gen = genalnum()
        self.map = {}
        self.recurse_guard = set()

    def name(self, typ, depth=0, max_depth=1):
        typ = typ.find()
        if isinstance(typ, TVar):
            if typ not in self.map:
                self.map[typ] = "'%s" % next(self.gen)
            return self.map[typ]
        elif isinstance(typ, TInstance):
            if typ in self.recurse_guard or depth >= max_depth:
                return "<instance {}>".format(typ.name)
            elif len(typ.attributes) > 0:
                self.recurse_guard.add(typ)
                attrs = ",\n\t\t".join(["{}: {}".format(attr, self.name(typ.attributes[attr],
                                                                        depth + 1))
                                      for attr in typ.attributes])
                return "<instance {} {{\n\t\t{}\n\t}}>".format(typ.name, attrs)
            else:
                self.recurse_guard.add(typ)
                return "<instance {} {{}}>".format(typ.name)
        elif isinstance(typ, TMono):
            if typ.name in self.custom_printers:
                return self.custom_printers[typ.name](typ, self, depth + 1, max_depth)
            elif typ.params == {}:
                return typ.name
            else:
                return "%s(%s)" % (typ.name, ", ".join(
                    ["%s=%s" % (k, self.name(typ.params[k], depth + 1)) for k in typ.params]))
        elif isinstance(typ, TTuple):
            if len(typ.elts) == 1:
                return "(%s,)" % self.name(typ.elts[0], depth + 1)
            else:
                return "(%s)" % ", ".join([self.name(typ, depth + 1) for typ in typ.elts])
        elif isinstance(typ, (TFunction, TCFunction)):
            args = []
            args += [ "%s:%s" % (arg, self.name(typ.args[arg], depth + 1))
                     for arg in typ.args]
            args += ["?%s:%s" % (arg, self.name(typ.optargs[arg], depth + 1))
                     for arg in typ.optargs]
            signature = "(%s)->%s" % (", ".join(args), self.name(typ.ret, depth + 1))

            delay = typ.delay.find()
            if isinstance(delay, TVar):
                signature += " delay({})".format(self.name(delay, depth + 1))
            elif not (delay.is_fixed() and iodelay.is_zero(delay.duration)):
                signature += " " + self.name(delay, depth + 1)

            if isinstance(typ, TCFunction):
                return "[ffi {}]{}".format(repr(typ.name), signature)
            elif isinstance(typ, TFunction):
                return signature
        elif isinstance(typ, TRPC):
            return "[rpc{} #{}](...)->{}".format(typ.service,
                                                 " async" if typ.is_async else "",
                                                 self.name(typ.ret, depth + 1))
        elif isinstance(typ, TBuiltinFunction):
            return "<function {}>".format(typ.name)
        elif isinstance(typ, (TConstructor, TExceptionConstructor)):
            if typ in self.recurse_guard or depth >= max_depth:
                return "<constructor {}>".format(typ.name)
            elif len(typ.attributes) > 0:
                self.recurse_guard.add(typ)
                attrs = ", ".join(["{}: {}".format(attr, self.name(typ.attributes[attr],
                                                                   depth + 1))
                                   for attr in typ.attributes])
                return "<constructor {} {{{}}}>".format(typ.name, attrs)
            else:
                self.recurse_guard.add(typ)
                return "<constructor {} {{}}>".format(typ.name)
        elif isinstance(typ, TBuiltin):
            return "<builtin {}>".format(typ.name)
        elif isinstance(typ, TValue):
            return repr(typ.value)
        elif isinstance(typ, TDelay):
            if typ.is_fixed():
                return "delay({} mu)".format(typ.duration)
            elif typ.is_indeterminate():
                return "delay(?)"
            else:
                assert False
        else:
            assert False
