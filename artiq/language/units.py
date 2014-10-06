from fractions import Fraction as _Fraction


_prefixes_str = "pnum_kMG"
_smallest_prefix = _Fraction(1, 10**12)


def mul_dimension(l, r):
    if l is None:
        return r
    if r is None:
        return l
    if {l, r} == {"Hz", "s"}:
        return None


def _rmul_dimension(l, r):
    return mul_dimension(r, l)


def div_dimension(l, r):
    if l == r:
        return None
    if r is None:
        return l
    if l is None:
        if r == "s":
            return "Hz"
        if r == "Hz":
            return "s"


def _rdiv_dimension(l, r):
    return div_dimension(r, l)


def addsub_dimension(x, y):
    if x == y:
        return x
    else:
        return None


def _format(amount, unit):
    if amount is NotImplemented:
        return NotImplemented
    if unit is None:
        return amount
    else:
        return Quantity(amount, unit)


class Quantity:
    """Represents an amount in a given fundamental unit (identified by a
    string).

    The amount can be of any Python numerical type (integer, float,
    Fraction, ...).
    Arithmetic operations and comparisons are directly delegated to the
    underlying numerical types.

    """
    def __init__(self, amount, unit):
        self.amount = amount
        self.unit = unit

    def __repr__(self):
        r_amount = self.amount
        if isinstance(r_amount, int) or isinstance(r_amount, _Fraction):
            r_prefix = 0
            r_amount = r_amount/_smallest_prefix
            if r_amount:
                numerator = r_amount.numerator
                while numerator % 1000 == 0 and r_prefix < len(_prefixes_str):
                    numerator /= 1000
                    r_amount /= 1000
                    r_prefix += 1
            prefix_str = _prefixes_str[r_prefix]
            if prefix_str == "_":
                prefix_str = ""
            return str(r_amount) + " " + prefix_str + self.unit
        else:
            return str(r_amount) + " " + self.unit

    # mul/div
    def _binop(self, other, opf_name, dim_function):
        opf = getattr(self.amount, opf_name)
        if isinstance(other, Quantity):
            amount = opf(other.amount)
            unit = dim_function(self.unit, other.unit)
        else:
            amount = opf(other)
            unit = dim_function(self.unit, None)
        return _format(amount, unit)

    def __mul__(self, other):
        return self._binop(other, "__mul__", mul_dimension)

    def __rmul__(self, other):
        return self._binop(other, "__rmul__", _rmul_dimension)

    def __truediv__(self, other):
        return self._binop(other, "__truediv__", div_dimension)

    def __rtruediv__(self, other):
        return self._binop(other, "__rtruediv__", _rdiv_dimension)

    def __floordiv__(self, other):
        return self._binop(other, "__floordiv__", div_dimension)

    def __rfloordiv__(self, other):
        return self._binop(other, "__rfloordiv__", _rdiv_dimension)

    # unary ops
    def __neg__(self):
        return Quantity(self.amount.__neg__(), self.unit)

    def __pos__(self):
        return Quantity(self.amount.__pos__(), self.unit)

    # add/sub
    def __add__(self, other):
        return self._binop(other, "__add__", addsub_dimension)

    def __radd__(self, other):
        return self._binop(other, "__radd__", addsub_dimension)

    def __sub__(self, other):
        return self._binop(other, "__sub__", addsub_dimension)

    def __rsub__(self, other):
        return self._binop(other, "__rsub__", addsub_dimension)

    def __mod__(self, other):
        return self._binop(other, "__mod__", addsub_dimension)

    def __rmod__(self, other):
        return self._binop(other, "__rmod__", addsub_dimension)

    # comparisons
    def _cmp(self, other, opf_name):
        if isinstance(other, Quantity):
            other = other.amount
        return getattr(self.amount, opf_name)(other)

    def __lt__(self, other):
        return self._cmp(other, "__lt__")

    def __le__(self, other):
        return self._cmp(other, "__le__")

    def __eq__(self, other):
        return self._cmp(other, "__eq__")

    def __ne__(self, other):
        return self._cmp(other, "__ne__")

    def __gt__(self, other):
        return self._cmp(other, "__gt__")

    def __ge__(self, other):
        return self._cmp(other, "__ge__")


def _register_unit(unit, prefixes):
    amount = _smallest_prefix
    for prefix in _prefixes_str:
        if prefix in prefixes:
            quantity = Quantity(amount, unit)
            full_name = prefix + unit if prefix != "_" else unit
            globals()[full_name] = quantity
        amount *= 1000

_register_unit("s", "pnum_")
_register_unit("Hz", "_kMG")
