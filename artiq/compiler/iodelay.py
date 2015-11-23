"""
The :mod:`iodelay` module contains the classes describing
the statically inferred RTIO delay arising from executing
a function.
"""

from functools import reduce

class Expr:
    def __add__(lhs, rhs):
        assert isinstance(rhs, Expr)
        return Add(lhs, rhs)
    __iadd__ = __add__

    def __sub__(lhs, rhs):
        assert isinstance(rhs, Expr)
        return Sub(lhs, rhs)
    __isub__ = __sub__

    def __mul__(lhs, rhs):
        assert isinstance(rhs, Expr)
        return Mul(lhs, rhs)
    __imul__ = __mul__

    def __truediv__(lhs, rhs):
        assert isinstance(rhs, Expr)
        return TrueDiv(lhs, rhs)
    __itruediv__ = __truediv__

    def __floordiv__(lhs, rhs):
        assert isinstance(rhs, Expr)
        return FloorDiv(lhs, rhs)
    __ifloordiv__ = __floordiv__

    def __ne__(lhs, rhs):
        return not (lhs == rhs)

    def free_vars(self):
        return set()

    def fold(self, vars=None):
        return self

class Const(Expr):
    _priority = 1

    def __init__(self, value):
        assert isinstance(value, (int, float))
        self.value = value

    def __str__(self):
        return str(self.value)

    def __eq__(lhs, rhs):
        return rhs.__class__ == lhs.__class__ and lhs.value == rhs.value

    def eval(self, env):
        return self.value

class Var(Expr):
    _priority = 1

    def __init__(self, name):
        assert isinstance(name, str)
        self.name = name

    def __str__(self):
        return self.name

    def __eq__(lhs, rhs):
        return rhs.__class__ == lhs.__class__ and lhs.name == rhs.name

    def free_vars(self):
        return {self.name}

    def fold(self, vars=None):
        if vars is not None and self.name in vars:
            return vars[self.name]
        else:
            return self

class Conv(Expr):
    _priority = 1

    def __init__(self, operand, ref_period):
        assert isinstance(operand, Expr)
        assert isinstance(ref_period, float)
        self.operand, self.ref_period = operand, ref_period

    def __eq__(lhs, rhs):
        return rhs.__class__ == lhs.__class__ and \
            lhs.ref_period == rhs.ref_period and \
            lhs.operand == rhs.operand

    def free_vars(self):
        return self.operand.free_vars()

class MUToS(Conv):
    def __str__(self):
        return "mu->s({})".format(self.operand)

    def eval(self, env):
        return self.operand.eval(env) * self.ref_period

    def fold(self, vars=None):
        operand = self.operand.fold(vars)
        if isinstance(operand, Const):
            return Const(operand.value * self.ref_period)
        else:
            return MUToS(operand, ref_period=self.ref_period)

class SToMU(Conv):
    def __str__(self):
        return "s->mu({})".format(self.operand)

    def eval(self, env):
        return int(self.operand.eval(env) / self.ref_period)

    def fold(self, vars=None):
        operand = self.operand.fold(vars)
        if isinstance(operand, Const):
            return Const(int(operand.value / self.ref_period))
        else:
            return SToMU(operand, ref_period=self.ref_period)

class BinOp(Expr):
    def __init__(self, lhs, rhs):
        self.lhs, self.rhs = lhs, rhs

    def __str__(self):
        lhs = "({})".format(self.lhs) if self.lhs._priority > self._priority else str(self.lhs)
        rhs = "({})".format(self.rhs) if self.rhs._priority > self._priority else str(self.rhs)
        return "{} {} {}".format(lhs, self._symbol, rhs)

    def __eq__(lhs, rhs):
        return rhs.__class__ == lhs.__class__ and lhs.lhs == rhs.lhs and lhs.rhs == rhs.rhs

    def eval(self, env):
        return self.__class__._op(self.lhs.eval(env), self.rhs.eval(env))

    def free_vars(self):
        return self.lhs.free_vars() | self.rhs.free_vars()

    def _fold_binop(self, lhs, rhs):
        if isinstance(lhs, Const) and lhs.__class__ == rhs.__class__:
            return Const(self.__class__._op(lhs.value, rhs.value))
        elif isinstance(lhs, (MUToS, SToMU)) and lhs.__class__ == rhs.__class__:
            return lhs.__class__(self.__class__(lhs.operand, rhs.operand),
                                 ref_period=lhs.ref_period).fold()
        else:
            return self.__class__(lhs, rhs)

    def fold(self, vars=None):
        return self._fold_binop(self.lhs.fold(vars), self.rhs.fold(vars))

class BinOpFixpoint(BinOp):
    def _fold_binop(self, lhs, rhs):
        if isinstance(lhs, Const) and lhs.value == self._fixpoint:
            return rhs
        elif isinstance(rhs, Const) and rhs.value == self._fixpoint:
            return lhs
        else:
            return super()._fold_binop(lhs, rhs)

class Add(BinOpFixpoint):
    _priority = 2
    _symbol   = "+"
    _op       = lambda a, b: a + b
    _fixpoint = 0

class Mul(BinOpFixpoint):
    _priority = 1
    _symbol   = "*"
    _op       = lambda a, b: a * b
    _fixpoint = 1

class Sub(BinOp):
    _priority = 2
    _symbol   = "-"
    _op       = lambda a, b: a - b

    def _fold_binop(self, lhs, rhs):
        if isinstance(rhs, Const) and rhs.value == 0:
            return lhs
        else:
            return super()._fold_binop(lhs, rhs)

class Div(BinOp):
    def _fold_binop(self, lhs, rhs):
        if isinstance(rhs, Const) and rhs.value == 1:
            return lhs
        else:
            return super()._fold_binop(lhs, rhs)

class TrueDiv(Div):
    _priority = 1
    _symbol   = "/"
    _op       = lambda a, b: a / b if b != 0 else 0

class FloorDiv(Div):
    _priority = 1
    _symbol   = "//"
    _op       = lambda a, b: a // b if b != 0 else 0

class Max(Expr):
    _priority = 1

    def __init__(self, operands):
        assert isinstance(operands, list)
        assert all([isinstance(operand, Expr) for operand in operands])
        assert operands != []
        self.operands = operands

    def __str__(self):
        return "max({})".format(", ".join([str(operand) for operand in self.operands]))

    def __eq__(lhs, rhs):
        return rhs.__class__ == lhs.__class__ and lhs.operands == rhs.operands

    def free_vars(self):
        return reduce(lambda a, b: a | b, [operand.free_vars() for operand in self.operands])

    def eval(self, env):
        return max([operand.eval() for operand in self.operands])

    def fold(self, vars=None):
        consts, exprs = [], []
        for operand in self.operands:
            operand = operand.fold(vars)
            if isinstance(operand, Const):
                consts.append(operand.value)
            elif operand not in exprs:
                exprs.append(operand)
        if len(consts) > 0:
            exprs.append(Const(max(consts)))
        if len(exprs) == 1:
            return exprs[0]
        else:
            return Max(exprs)

def is_const(expr, value=None):
    expr = expr.fold()
    if value is None:
        return isinstance(expr, Const)
    else:
        return isinstance(expr, Const) and expr.value == value

def is_zero(expr):
    return is_const(expr, 0)
