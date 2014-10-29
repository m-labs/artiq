import ast
import operator

from artiq.transforms.tools import *
from artiq.language.core import int64, round64


_ast_unops = {
    ast.Invert: operator.inv,
    ast.Not: operator.not_,
    ast.UAdd: operator.pos,
    ast.USub: operator.neg
}


_ast_binops = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.LShift: operator.lshift,
    ast.RShift: operator.rshift,
    ast.BitOr: operator.or_,
    ast.BitXor: operator.xor,
    ast.BitAnd: operator.and_
}

_ast_cmpops = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge
}

_ast_boolops = {
    ast.Or: lambda x, y: x or y,
    ast.And: lambda x, y: x and y
}


class _ConstantFolder(ast.NodeTransformer):
    def visit_UnaryOp(self, node):
        self.generic_visit(node)
        try:
            operand = eval_constant(node.operand)
        except NotConstant:
            return node
        try:
            op = _ast_unops[type(node.op)]
        except KeyError:
            return node
        try:
            result = value_to_ast(op(operand))
        except:
            return node
        return ast.copy_location(result, node)

    def visit_BinOp(self, node):
        self.generic_visit(node)
        try:
            left, right = eval_constant(node.left), eval_constant(node.right)
        except NotConstant:
            return node
        try:
            op = _ast_binops[type(node.op)]
        except KeyError:
            return node
        try:
            result = value_to_ast(op(left, right))
        except:
            return node
        return ast.copy_location(result, node)

    def visit_Compare(self, node):
        self.generic_visit(node)
        try:
            operands = [eval_constant(node.left)]
        except NotConstant:
            operands = [node.left]
        ops = []
        for op, right_ast in zip(node.ops, node.comparators):
            try:
                right = eval_constant(right_ast)
            except NotConstant:
                right = right_ast
            if (not isinstance(operands[-1], ast.AST)
                    and not isinstance(right, ast.AST)):
                left = operands.pop()
                operands.append(_ast_cmpops[type(op)](left, right))
            else:
                ops.append(op)
                operands.append(right_ast)
        operands = [operand if isinstance(operand, ast.AST)
                    else ast.copy_location(value_to_ast(operand), node)
                    for operand in operands]
        if len(operands) == 1:
            return operands[0]
        else:
            node.left = operands[0]
            node.right = operands[1:]
            node.ops = ops
            return node

    def visit_BoolOp(self, node):
        self.generic_visit(node)
        new_values = []
        for value in node.values:
            try:
                value_c = eval_constant(value)
            except NotConstant:
                new_values.append(value)
            else:
                if new_values and not isinstance(new_values[-1], ast.AST):
                    op = _ast_boolops[type(node.op)]
                    new_values[-1] = op(new_values[-1], value_c)
                else:
                    new_values.append(value_c)
        new_values = [v if isinstance(v, ast.AST) else value_to_ast(v)
                      for v in new_values]
        if len(new_values) > 1:
            node.values = new_values
            return node
        else:
            return new_values[0]

    def visit_Call(self, node):
        self.generic_visit(node)
        fn = node.func.id
        constant_ops = {
            "int": int,
            "int64": int64,
            "round": round,
            "round64": round64
        }
        if fn in constant_ops:
            try:
                arg = eval_constant(node.args[0])
            except NotConstant:
                return node
            result = value_to_ast(constant_ops[fn](arg))
            return ast.copy_location(result, node)
        else:
            return node


def fold_constants(node):
    _ConstantFolder().visit(node)
