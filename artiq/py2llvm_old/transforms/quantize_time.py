"""
This transform turns calls to delay() that use non-integer time
expressed in seconds into calls to delay_mu() that use int64 time
expressed in multiples of ref_period.

It does so by inserting multiplication/division/rounding operations around
those calls.

The seconds_to_mu and mu_to_seconds core language functions are also
implemented here, as well as watchdog to syscall conversion.
"""

import ast

from artiq.transforms.tools import value_to_ast


def _seconds_to_mu(ref_period, node):
    divided = ast.copy_location(
        ast.BinOp(left=node,
                  op=ast.Div(),
                  right=value_to_ast(ref_period)),
        node)
    return ast.copy_location(
        ast.Call(func=ast.Name("round64", ast.Load()),
                 args=[divided],
                 keywords=[], starargs=[], kwargs=[]),
        divided)


def _mu_to_seconds(ref_period, node):
    return ast.copy_location(
        ast.BinOp(left=node,
                  op=ast.Mult(),
                  right=value_to_ast(ref_period)),
        node)


class _TimeQuantizer(ast.NodeTransformer):
    def __init__(self, ref_period):
        self.ref_period = ref_period
        self.watchdog_id_counter = 0

    def visit_Call(self, node):
        funcname = node.func.id
        if funcname == "delay":
            node.func.id = "delay_mu"
            if (isinstance(node.args[0], ast.Call)
                    and node.args[0].func.id == "mu_to_seconds"):
                # optimize:
                # delay(mu_to_seconds(x)) -> delay_mu(x)
                node.args[0] = self.visit(node.args[0].args[0])
            else:
                node.args[0] = _seconds_to_mu(self.ref_period,
                                              self.visit(node.args[0]))
            return node
        elif funcname == "seconds_to_mu":
                return _seconds_to_mu(self.ref_period,
                                       self.visit(node.args[0]))
        elif funcname == "mu_to_seconds":
            return _mu_to_seconds(self.ref_period,
                                   self.visit(node.args[0]))
        else:
            self.generic_visit(node)
            return node

    def visit_With(self, node):
        self.generic_visit(node)
        if (isinstance(node.items[0].context_expr, ast.Call)
                and node.items[0].context_expr.func.id == "watchdog"):

            idname = "__watchdog_id_" + str(self.watchdog_id_counter)
            self.watchdog_id_counter += 1

            time = ast.BinOp(left=node.items[0].context_expr.args[0],
                             op=ast.Mult(),
                             right=ast.Num(1000))
            time_int = ast.Call(
                func=ast.Name("round", ast.Load()),
                args=[time],
                keywords=[], starargs=None, kwargs=None)
            syscall_set = ast.Call(
                func=ast.Name("syscall", ast.Load()),
                args=[ast.Str("watchdog_set"), time_int],
                keywords=[], starargs=None, kwargs=None)
            stmt_set = ast.copy_location(
                ast.Assign(targets=[ast.Name(idname, ast.Store())],
                           value=syscall_set),
                node)

            syscall_clear = ast.Call(
                func=ast.Name("syscall", ast.Load()),
                args=[ast.Str("watchdog_clear"),
                              ast.Name(idname, ast.Load())],
                keywords=[], starargs=None, kwargs=None)
            stmt_clear = ast.copy_location(ast.Expr(syscall_clear), node)

            node.items[0] = ast.withitem(
                context_expr=ast.Name(id="sequential",
                ctx=ast.Load()),
                optional_vars=None)
            node.body = [
                stmt_set,
                ast.Try(body=node.body,
                        handlers=[],
                        orelse=[],
                        finalbody=[stmt_clear])
            ]
        return node


def quantize_time(func_def, ref_period):
    _TimeQuantizer(ref_period).visit(func_def)
