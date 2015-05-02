"""
This transform implements time management functions (delay/now/at)
using an accumulator 'now' and simple replacement rules:

    delay(t) ->  now += t
    now()    ->  now
    at(t)    ->  now = t

Time parameters must be quantized to integers before running this transform.
The accumulator is initialized to an int64 value at the beginning of the
output function.

"""

import ast


class _TimeLowerer(ast.NodeTransformer):
    def visit_Call(self, node):
        if node.func.id == "now":
            return ast.copy_location(ast.Name("now", ast.Load()), node)
        else:
            self.generic_visit(node)
            return node

    def visit_Expr(self, node):
        r = node
        if isinstance(node.value, ast.Call):
            funcname = node.value.func.id
            if funcname == "delay":
                r = ast.copy_location(
                    ast.AugAssign(target=ast.Name("now", ast.Store()),
                                  op=ast.Add(),
                                  value=node.value.args[0]),
                    node)
            elif funcname == "at":
                r = ast.copy_location(
                    ast.Assign(targets=[ast.Name("now", ast.Store())],
                               value=node.value.args[0]),
                    node)
        self.generic_visit(r)
        return r


def lower_time(func_def):
    _TimeLowerer().visit(func_def)
    call_init = ast.Call(
        func=ast.Name("syscall", ast.Load()),
        args=[ast.Str("now_init")],
        keywords=[], starargs=None, kwargs=None)
    stmt_init = ast.Assign(targets=[ast.Name("now", ast.Store())],
        value=call_init)
    call_save = ast.Call(
        func=ast.Name("syscall", ast.Load()),
        args=[ast.Str("now_save"), ast.Name("now", ast.Load())],
        keywords=[], starargs=None, kwargs=None)
    stmt_save = ast.Expr(call_save)
    func_def.body = [
        stmt_init,
        ast.Try(body=func_def.body,
                handlers=[],
                orelse=[],
                finalbody=[stmt_save])
    ]
