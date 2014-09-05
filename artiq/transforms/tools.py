import ast
from fractions import Fraction

from artiq.language import core as core_language
from artiq.language import units


def eval_ast(expr, symdict=dict()):
    if not isinstance(expr, ast.Expression):
        expr = ast.copy_location(ast.Expression(expr), expr)
    ast.fix_missing_locations(expr)
    code = compile(expr, "<ast>", "eval")
    return eval(code, symdict)


def value_to_ast(value):
    if isinstance(value, core_language.int64):  # must be before int
        return ast.Call(
            func=ast.Name("int64", ast.Load()),
            args=[ast.Num(int(value))],
            keywords=[], starargs=None, kwargs=None)
    elif isinstance(value, int):
        return ast.Num(value)
    elif isinstance(value, Fraction):
        return ast.Call(
            func=ast.Name("Fraction", ast.Load()),
            args=[ast.Num(value.numerator), ast.Num(value.denominator)],
            keywords=[], starargs=None, kwargs=None)
    elif isinstance(value, str):
        return ast.Str(value)
    else:
        for kg in core_language.kernel_globals:
            if value is getattr(core_language, kg):
                return ast.Name(kg, ast.Load())
        if isinstance(value, units.Quantity):
            return ast.Call(
                func=ast.Name("Quantity", ast.Load()),
                args=[value_to_ast(value.amount),
                      ast.Name(value.unit.name+"_unit", ast.Load())],
                keywords=[], starargs=None, kwargs=None)
        return None


class NotConstant(Exception):
    pass


def eval_constant(node):
    if isinstance(node, ast.Num):
        return node.n
    elif isinstance(node, ast.Str):
        return node.s
    elif isinstance(node, ast.Call):
        funcname = node.func.id
        if funcname == "Fraction":
            numerator = eval_constant(node.args[0])
            denominator = eval_constant(node.args[1])
            return Fraction(numerator, denominator)
        elif funcname == "Quantity":
            amount, unit = node.args
            amount = eval_constant(amount)
            try:
                unit = getattr(units, unit.id)
            except:
                raise NotConstant
            return units.Quantity(amount, unit)
        else:
            raise NotConstant
    else:
        raise NotConstant
