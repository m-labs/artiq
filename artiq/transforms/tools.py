import ast
from fractions import Fraction

from artiq.language import core as core_language
from artiq.language import units


embeddable_funcs = (
    core_language.delay_mu, core_language.at_mu, core_language.now_mu,
    core_language.delay,
    core_language.seconds_to_mu, core_language.mu_to_seconds,
    core_language.syscall, core_language.watchdog,
    range, bool, int, float, round, len,
    core_language.int64, core_language.round64,
    Fraction, core_language.EncodedException
)
embeddable_func_names = {func.__name__ for func in embeddable_funcs}


def is_embeddable(func):
    for ef in embeddable_funcs:
        if func is ef:
            return True
    return False


def eval_ast(expr, symdict=dict()):
    if not isinstance(expr, ast.Expression):
        expr = ast.copy_location(ast.Expression(expr), expr)
    ast.fix_missing_locations(expr)
    code = compile(expr, "<ast>", "eval")
    return eval(code, symdict)


class NotASTRepresentable(Exception):
    pass


def value_to_ast(value):
    if isinstance(value, core_language.int64):  # must be before int
        return ast.Call(
            func=ast.Name("int64", ast.Load()),
            args=[ast.Num(int(value))],
            keywords=[], starargs=None, kwargs=None)
    elif isinstance(value, bool) or value is None:
        # must also be before int
        # isinstance(True/False, int) == True
        return ast.NameConstant(value)
    elif isinstance(value, (int, float)):
        return ast.Num(value)
    elif isinstance(value, Fraction):
        return ast.Call(
            func=ast.Name("Fraction", ast.Load()),
            args=[ast.Num(value.numerator), ast.Num(value.denominator)],
            keywords=[], starargs=None, kwargs=None)
    elif isinstance(value, str):
        return ast.Str(value)
    elif isinstance(value, list):
        elts = [value_to_ast(elt) for elt in value]
        return ast.List(elts, ast.Load())
    else:
        for kg in core_language.kernel_globals:
            if value is getattr(core_language, kg):
                return ast.Name(kg, ast.Load())
        raise NotASTRepresentable(str(value))


class NotConstant(Exception):
    pass


def eval_constant(node):
    if isinstance(node, ast.Num):
        return node.n
    elif isinstance(node, ast.Str):
        return node.s
    elif isinstance(node, ast.NameConstant):
        return node.value
    elif isinstance(node, ast.Call):
        funcname = node.func.id
        if funcname == "int64":
            return core_language.int64(eval_constant(node.args[0]))
        elif funcname == "Fraction":
            numerator = eval_constant(node.args[0])
            denominator = eval_constant(node.args[1])
            return Fraction(numerator, denominator)
        else:
            raise NotConstant
    else:
        raise NotConstant


_replaceable_funcs = {
    "bool", "int", "float", "round",
    "int64", "round64", "Fraction",
    "seconds_to_mu", "mu_to_seconds"
}


def _is_ref_transparent(dependencies, expr):
    if isinstance(expr, (ast.NameConstant, ast.Num, ast.Str)):
        return True
    elif isinstance(expr, ast.Name):
        dependencies.add(expr.id)
        return True
    elif isinstance(expr, ast.UnaryOp):
        return _is_ref_transparent(dependencies, expr.operand)
    elif isinstance(expr, ast.BinOp):
        return (_is_ref_transparent(dependencies, expr.left)
                and _is_ref_transparent(dependencies, expr.right))
    elif isinstance(expr, ast.BoolOp):
        return all(_is_ref_transparent(dependencies, v) for v in expr.values)
    elif isinstance(expr, ast.Call):
        return (expr.func.id in _replaceable_funcs and
                all(_is_ref_transparent(dependencies, arg)
                    for arg in expr.args))
    else:
        return False


def is_ref_transparent(expr):
    dependencies = set()
    if _is_ref_transparent(dependencies, expr):
        return True, dependencies
    else:
        return False, None


class _NodeCounter(ast.NodeVisitor):
    def __init__(self):
        self.count = 0

    def generic_visit(self, node):
        self.count += 1
        ast.NodeVisitor.generic_visit(self, node)


def count_all_nodes(node):
    nc = _NodeCounter()
    nc.visit(node)
    return nc.count
