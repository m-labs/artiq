"""
:class:`IRGenerator` transforms typed AST into ARTIQ intermediate
representation.
"""

from collections import OrderedDict
from pythonparser import algorithm, diagnostic, ast
from .. import types, builtins, ir

# We put some effort in keeping generated IR readable,
# i.e. with a more or less linear correspondence to the source.
# This is why basic blocks sometimes seem to be produced in an odd order.
class IRGenerator(algorithm.Visitor):
    def __init__(self, module_name, engine):
        self.engine = engine
        self.functions = []
        self.name = [module_name]
        self.current_function = None
        self.current_block = None
        self.break_target, self.continue_target = None, None

    def add_block(self):
        block = ir.BasicBlock([])
        self.current_function.add(block)
        return block

    def append(self, insn):
        return self.current_block.append(insn)

    def terminate(self, insn):
        if not self.current_block.is_terminated():
            self.append(insn)

    def visit(self, obj):
        if isinstance(obj, list):
            for elt in obj:
                self.visit(elt)
                if self.current_block.is_terminated():
                    break
        elif isinstance(obj, ast.AST):
            return self._visit_one(obj)

    def visit_function(self, name, typ, inner):
        try:
            old_name, self.name = self.name, self.name + [name]

            args = []
            for arg_name in typ.args:
                args.append(ir.Argument(typ.args[arg_name], arg_name))
            for arg_name in typ.optargs:
                args.append(ir.Argument(ir.TSSAOption(typ.optargs[arg_name]), arg_name))

            func = ir.Function(typ, ".".join(self.name), args)
            self.functions.append(func)
            old_func, self.current_function = self.current_function, func

            self.current_block = self.add_block()
            inner()
        finally:
            self.name = old_name
            self.current_function = old_func

    def visit_ModuleT(self, node):
        def inner():
            self.generic_visit(node)

            return_value = ir.Constant(None, builtins.TNone())
            self.terminate(ir.Return(return_value))

        typ = types.TFunction(OrderedDict(), OrderedDict(), builtins.TNone())
        self.visit_function('__modinit__', typ, inner)

    def visit_FunctionDefT(self, node):
        self.visit_function(node.name, node.signature_type.find(),
                            lambda: self.generic_visit(node))

    def visit_Return(self, node):
        if node.value is None:
            return_value = ir.Constant(None, builtins.TNone())
            self.append(ir.Return(return_value))
        else:
            expr = self.append(ir.Eval(node.value))
            self.append(ir.Return(expr))

    def visit_Expr(self, node):
        self.append(ir.Eval(node.value))

    # Assign
    # AugAssign

    def visit_If(self, node):
        cond = self.append(ir.Eval(node.test))
        head = self.current_block

        if_true = self.add_block()
        self.current_block = if_true
        self.visit(node.body)

        if_false = self.add_block()
        self.current_block = if_false
        self.visit(node.orelse)

        tail = self.add_block()
        self.current_block = tail
        if not if_true.is_terminated():
            if_true.append(ir.Branch(tail))
        if not if_false.is_terminated():
            if_false.append(ir.Branch(tail))
        head.append(ir.BranchIf(cond, if_true, if_false))

    def visit_While(self, node):
        try:
            head = self.add_block()
            self.append(ir.Branch(head))
            self.current_block = head

            tail_tramp = self.add_block()
            old_break, self.break_target = self.break_target, tail_tramp

            body = self.add_block()
            old_continue, self.continue_target = self.continue_target, body
            self.current_block = body
            self.visit(node.body)

            tail = self.add_block()
            self.current_block = tail
            self.visit(node.orelse)

            cond = head.append(ir.Eval(node.test))
            head.append(ir.BranchIf(cond, body, tail))
            if not body.is_terminated():
                body.append(ir.Branch(tail))
            tail_tramp.append(ir.Branch(tail))
        finally:
            self.break_target = old_break
            self.continue_target = old_continue

    # For

    def visit_Break(self, node):
        self.append(ir.Branch(self.break_target))

    def visit_Continue(self, node):
        self.append(ir.Branch(self.continue_target))

    # Raise
    # Try

    # With
