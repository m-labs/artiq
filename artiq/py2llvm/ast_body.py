import ast
from llvm import core as lc

from artiq.py2llvm import values, base_types, fractions, arrays, iterators
from artiq.py2llvm.tools import is_terminated


_ast_unops = {
    ast.Invert: "o_inv",
    ast.Not: "o_not",
    ast.UAdd: "o_pos",
    ast.USub: "o_neg"
}

_ast_binops = {
    ast.Add: values.operators.add,
    ast.Sub: values.operators.sub,
    ast.Mult: values.operators.mul,
    ast.Div: values.operators.truediv,
    ast.FloorDiv: values.operators.floordiv,
    ast.Mod: values.operators.mod,
    ast.Pow: values.operators.pow,
    ast.LShift: values.operators.lshift,
    ast.RShift: values.operators.rshift,
    ast.BitOr: values.operators.or_,
    ast.BitXor: values.operators.xor,
    ast.BitAnd: values.operators.and_
}

_ast_cmps = {
    ast.Eq: values.operators.eq,
    ast.NotEq: values.operators.ne,
    ast.Lt: values.operators.lt,
    ast.LtE: values.operators.le,
    ast.Gt: values.operators.gt,
    ast.GtE: values.operators.ge
}


class Visitor:
    def __init__(self, env, ns, builder=None):
        self.env = env
        self.ns = ns
        self.builder = builder
        self._break_stack = []
        self._eid_stack = []

    # builder can be None for visit_expression
    def visit_expression(self, node):
        method = "_visit_expr_" + node.__class__.__name__
        try:
            visitor = getattr(self, method)
        except AttributeError:
            raise NotImplementedError("Unsupported node '{}' in expression"
                                      .format(node.__class__.__name__))
        return visitor(node)

    def _visit_expr_Name(self, node):
        try:
            r = self.ns[node.id]
        except KeyError:
            raise NameError("Name '{}' is not defined".format(node.id))
        return r

    def _visit_expr_NameConstant(self, node):
        v = node.value
        if v is None:
            r = base_types.VNone()
        elif isinstance(v, bool):
            r = base_types.VBool()
        else:
            raise NotImplementedError
        if self.builder is not None:
            r.set_const_value(self.builder, v)
        return r

    def _visit_expr_Num(self, node):
        n = node.n
        if isinstance(n, int):
            if abs(n) < 2**31:
                r = base_types.VInt()
            else:
                r = base_types.VInt(64)
        elif isinstance(n, float):
            r = base_types.VFloat()
        else:
            raise NotImplementedError
        if self.builder is not None:
            r.set_const_value(self.builder, n)
        return r

    def _visit_expr_UnaryOp(self, node):
        value = self.visit_expression(node.operand)
        return getattr(value, _ast_unops[type(node.op)])(self.builder)

    def _visit_expr_BinOp(self, node):
        return _ast_binops[type(node.op)](self.visit_expression(node.left),
                                          self.visit_expression(node.right),
                                          self.builder)

    def _visit_expr_Compare(self, node):
        comparisons = []
        old_comparator = self.visit_expression(node.left)
        for op, comparator_a in zip(node.ops, node.comparators):
            comparator = self.visit_expression(comparator_a)
            comparison = _ast_cmps[type(op)](old_comparator, comparator,
                                            self.builder)
            comparisons.append(comparison)
            old_comparator = comparator
        r = comparisons[0]
        for comparison in comparisons[1:]:
            r = values.operators.and_(r, comparison)
        return r

    def _visit_expr_Call(self, node):
        fn = node.func.id
        if fn in {"bool", "int", "int64", "round", "round64", "float"}:
            value = self.visit_expression(node.args[0])
            return getattr(value, "o_"+fn)(self.builder)
        elif fn == "Fraction":
            r = fractions.VFraction()
            if self.builder is not None:
                numerator = self.visit_expression(node.args[0])
                denominator = self.visit_expression(node.args[1])
                r.set_value_nd(self.builder, numerator, denominator)
            return r
        elif fn == "array":
            element = self.visit_expression(node.args[0])
            if (isinstance(node.args[1], ast.Num)
                    and isinstance(node.args[1].n, int)):
                count = node.args[1].n
            else:
                raise ValueError("Array size must be integer and constant")
            return arrays.VArray(element, count)
        elif fn == "range":
            return iterators.IRange(
                self.builder,
                [self.visit_expression(arg) for arg in node.args])
        elif fn == "syscall":
            return self.env.build_syscall(
                node.args[0].s,
                [self.visit_expression(expr) for expr in node.args[1:]],
                self.builder)
        else:
            raise NameError("Function '{}' is not defined".format(fn))

    def _visit_expr_Attribute(self, node):
        value = self.visit_expression(node.value)
        return value.o_getattr(node.attr, self.builder)

    def _visit_expr_Subscript(self, node):
        value = self.visit_expression(node.value)
        if isinstance(node.slice, ast.Index):
            index = self.visit_expression(node.slice.value)
        else:
            raise NotImplementedError
        return value.o_subscript(index, self.builder)

    def visit_statements(self, stmts):
        for node in stmts:
            node_type = node.__class__.__name__
            method = "_visit_stmt_" + node_type
            try:
                visitor = getattr(self, method)
            except AttributeError:
                raise NotImplementedError("Unsupported node '{}' in statement"
                                          .format(node_type))
            visitor(node)
            if node_type in ("Return", "Break", "Continue"):
                break

    def _visit_stmt_Assign(self, node):
        val = self.visit_expression(node.value)
        for target in node.targets:
            target = self.visit_expression(target)
            target.set_value(self.builder, val)

    def _visit_stmt_AugAssign(self, node):
        target = self.visit_expression(node.target)
        right = self.visit_expression(node.value)
        val = _ast_binops[type(node.op)](target, right, self.builder)
        target.set_value(self.builder, val)

    def _visit_stmt_Expr(self, node):
        self.visit_expression(node.value)

    def _visit_stmt_If(self, node):
        function = self.builder.basic_block.function
        then_block = function.append_basic_block("i_then")
        else_block = function.append_basic_block("i_else")
        merge_block = function.append_basic_block("i_merge")

        condition = self.visit_expression(node.test).o_bool(self.builder)
        self.builder.cbranch(condition.auto_load(self.builder),
                             then_block, else_block)

        self.builder.position_at_end(then_block)
        self.visit_statements(node.body)
        if not is_terminated(self.builder.basic_block):
            self.builder.branch(merge_block)

        self.builder.position_at_end(else_block)
        self.visit_statements(node.orelse)
        if not is_terminated(self.builder.basic_block):
            self.builder.branch(merge_block)

        self.builder.position_at_end(merge_block)

    def _visit_stmt_While(self, node):
        function = self.builder.basic_block.function
        body_block = function.append_basic_block("w_body")
        else_block = function.append_basic_block("w_else")
        merge_block = function.append_basic_block("w_merge")
        self._break_stack.append(merge_block)

        condition = self.visit_expression(node.test).o_bool(self.builder)
        self.builder.cbranch(
            condition.auto_load(self.builder), body_block, else_block)

        self.builder.position_at_end(body_block)
        self.visit_statements(node.body)
        if not is_terminated(self.builder.basic_block):
            condition = self.visit_expression(node.test).o_bool(self.builder)
            self.builder.cbranch(
                condition.auto_load(self.builder), body_block, merge_block)

        self.builder.position_at_end(else_block)
        self.visit_statements(node.orelse)
        if not is_terminated(self.builder.basic_block):
            self.builder.branch(merge_block)

        self.builder.position_at_end(merge_block)
        self._break_stack.pop()

    def _visit_stmt_For(self, node):
        function = self.builder.basic_block.function
        body_block = function.append_basic_block("f_body")
        else_block = function.append_basic_block("f_else")
        merge_block = function.append_basic_block("f_merge")
        self._break_stack.append(merge_block)

        it = self.visit_expression(node.iter)
        target = self.visit_expression(node.target)
        itval = it.get_value_ptr()

        cont = it.o_next(self.builder)
        self.builder.cbranch(
            cont.auto_load(self.builder), body_block, else_block)

        self.builder.position_at_end(body_block)
        target.set_value(self.builder, itval)
        self.visit_statements(node.body)
        if not is_terminated(self.builder.basic_block):
            cont = it.o_next(self.builder)
            self.builder.cbranch(
                cont.auto_load(self.builder), body_block, merge_block)

        self.builder.position_at_end(else_block)
        self.visit_statements(node.orelse)
        if not is_terminated(self.builder.basic_block):
            self.builder.branch(merge_block)

        self.builder.position_at_end(merge_block)
        self._break_stack.pop()

    def _visit_stmt_Break(self, node):
        self.builder.branch(self._break_stack[-1])

    def _visit_stmt_Return(self, node):
        if node.value is None:
            val = base_types.VNone()
        else:
            val = self.visit_expression(node.value)
        if isinstance(val, base_types.VNone):
            self.builder.ret_void()
        else:
            self.builder.ret(val.auto_load(self.builder))

    def _visit_stmt_Pass(self, node):
        pass

    def _visit_stmt_Raise(self, node):
        if node.exc is None:
            eid = self._eid_stack[-1]
        else:
            eid = lc.Constant.int(lc.Type.int(), node.exc.args[0].n)
        self.env.build_raise(self.builder, eid)

    def _handle_exception(self, function, finally_block, propagate, handlers):
        eid = self.env.build_getid(self.builder)
        self._eid_stack.append(eid)
        self.builder.store(lc.Constant.int(lc.Type.int(1), 1), propagate)

        for handler in handlers:
            handled_exc_block = function.append_basic_block("try_exc_h")
            cont_exc_block = function.append_basic_block("try_exc_c")
            if handler.type is None:
                self.builder.branch(handled_exc_block)
            else:
                if isinstance(handler.type, ast.Tuple):
                    match = self.builder.icmp(
                        lc.ICMP_EQ, eid,
                        lc.Constant.int(lc.Type.int(),
                                        handler.type.elts[0].args[0].n))
                    for elt in handler.type.elts[1:]:
                        match = self.builder.or_(
                            match,
                            self.builder.icmp(
                                lc.ICMP_EQ, eid,
                                lc.Constant.int(lc.Type.int(), elt.args[0].n)))
                else:
                    match = self.builder.icmp(
                        lc.ICMP_EQ, eid,
                        lc.Constant.int(lc.Type.int(), handler.type.args[0].n))
                self.builder.cbranch(match, handled_exc_block, cont_exc_block)
            self.builder.position_at_end(handled_exc_block)
            self.builder.store(lc.Constant.int(lc.Type.int(1), 0), propagate)
            self.visit_statements(handler.body)
            if not is_terminated(self.builder.basic_block):
                self.builder.branch(finally_block)
            self.builder.position_at_end(cont_exc_block)
        self.builder.branch(finally_block)

        self._eid_stack.pop()
        return eid

    def _visit_stmt_Try(self, node):
        function = self.builder.basic_block.function
        noexc_block = function.append_basic_block("try_noexc")
        exc_block = function.append_basic_block("try_exc")
        finally_block = function.append_basic_block("try_finally")

        propagate = self.builder.alloca(lc.Type.int(1), name="propagate")
        self.builder.store(lc.Constant.int(lc.Type.int(1), 0), propagate)
        exception_occured = self.env.build_catch(self.builder)
        self.builder.cbranch(exception_occured, exc_block, noexc_block)

        self.builder.position_at_end(noexc_block)
        self.visit_statements(node.body)
        if not is_terminated(self.builder.basic_block):
            self.env.build_pop(self.builder, 1)
            self.visit_statements(node.orelse)
            if not is_terminated(self.builder.basic_block):
                self.builder.branch(finally_block)
        self.builder.position_at_end(exc_block)
        eid = self._handle_exception(function, finally_block, propagate,
                                     node.handlers)

        propagate_block = function.append_basic_block("try_propagate")
        merge_block = function.append_basic_block("try_merge")
        self.builder.position_at_end(finally_block)
        self.visit_statements(node.finalbody)
        if not is_terminated(self.builder.basic_block):
            self.builder.cbranch(
                self.builder.load(propagate),
                propagate_block, merge_block)
        self.builder.position_at_end(propagate_block)
        self.env.build_raise(self.builder, eid)
        self.builder.branch(merge_block)
        self.builder.position_at_end(merge_block)
