import ast

import llvmlite_or1k.ir as ll

from artiq.py2llvm import values, base_types, fractions, lists, iterators
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
    def __init__(self, runtime, ns, builder=None):
        self.runtime = runtime
        self.ns = ns
        self.builder = builder
        self._break_stack = []
        self._continue_stack = []
        self._active_exception_stack = []
        self._exception_level_stack = [0]

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

    def _visit_expr_BoolOp(self, node):
        if self.builder is not None:
            initial_block = self.builder.basic_block
            function = initial_block.function
            merge_block = function.append_basic_block("b_merge")

        test_blocks = []
        test_values = []
        for i, value in enumerate(node.values):
            if self.builder is not None:
                test_block = function.append_basic_block("b_{}_test".format(i))
                test_blocks.append(test_block)
                self.builder.position_at_end(test_block)
            test_values.append(self.visit_expression(value))

        result = test_values[0].new()
        for value in test_values[1:]:
            result.merge(value)

        if self.builder is not None:
            self.builder.position_at_end(initial_block)
            result.alloca(self.builder, "b_result")
            self.builder.branch(test_blocks[0])

            next_test_blocks = test_blocks[1:]
            next_test_blocks.append(None)
            for block, next_block, value in zip(test_blocks,
                                                next_test_blocks,
                                                test_values):
                self.builder.position_at_end(block)
                bval = value.o_bool(self.builder)
                result.auto_store(self.builder,
                                  value.auto_load(self.builder))
                if next_block is None:
                    self.builder.branch(merge_block)
                else:
                    if isinstance(node.op, ast.Or):
                        self.builder.cbranch(bval.auto_load(self.builder),
                                             merge_block,
                                             next_block)
                    elif isinstance(node.op, ast.And):
                        self.builder.cbranch(bval.auto_load(self.builder),
                                             next_block,
                                             merge_block)
                    else:
                        raise NotImplementedError
            self.builder.position_at_end(merge_block)

        return result

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
        if fn in {"bool", "int", "int64", "round", "round64", "float", "len"}:
            value = self.visit_expression(node.args[0])
            return getattr(value, "o_" + fn)(self.builder)
        elif fn == "Fraction":
            r = fractions.VFraction()
            if self.builder is not None:
                numerator = self.visit_expression(node.args[0])
                denominator = self.visit_expression(node.args[1])
                r.set_value_nd(self.builder, numerator, denominator)
            return r
        elif fn == "range":
            return iterators.IRange(
                self.builder,
                [self.visit_expression(arg) for arg in node.args])
        elif fn == "syscall":
            return self.runtime.build_syscall(
                node.args[0].s,
                [self.visit_expression(expr) for expr in node.args[1:]],
                self.builder)
        else:
            raise NameError("Function '{}' is not defined".format(fn))

    def _visit_expr_Attribute(self, node):
        value = self.visit_expression(node.value)
        return value.o_getattr(node.attr, self.builder)

    def _visit_expr_List(self, node):
        elts = [self.visit_expression(elt) for elt in node.elts]
        if elts:
            el_type = elts[0].new()
            for elt in elts[1:]:
                el_type.merge(elt)
        else:
            el_type = base_types.VNone()
        count = len(elts)
        r = lists.VList(el_type, count)
        r.elts = elts
        return r

    def _visit_expr_ListComp(self, node):
        if len(node.generators) != 1:
            raise NotImplementedError
        generator = node.generators[0]
        if not isinstance(generator, ast.comprehension):
            raise NotImplementedError
        if not isinstance(generator.target, ast.Name):
            raise NotImplementedError
        target = generator.target.id
        if not isinstance(generator.iter, ast.Call):
            raise NotImplementedError
        if not isinstance(generator.iter.func, ast.Name):
            raise NotImplementedError
        if generator.iter.func.id != "range":
            raise NotImplementedError
        if len(generator.iter.args) != 1:
            raise NotImplementedError
        if not isinstance(generator.iter.args[0], ast.Num):
            raise NotImplementedError
        count = generator.iter.args[0].n

        # Prevent incorrect use of the generator target, if it is defined in
        # the local function namespace.
        if target in self.ns:
            old_target_val = self.ns[target]
            del self.ns[target]
        else:
            old_target_val = None
        elt = self.visit_expression(node.elt)
        if old_target_val is not None:
            self.ns[target] = old_target_val

        el_type = elt.new()
        r = lists.VList(el_type, count)
        r.elt = elt
        return r

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

    def _bb_terminated(self):
        return is_terminated(self.builder.basic_block)

    def _visit_stmt_Assign(self, node):
        val = self.visit_expression(node.value)
        if isinstance(node.value, ast.List):
            if len(node.targets) > 1:
                raise NotImplementedError
            target = self.visit_expression(node.targets[0])
            target.set_count(self.builder, val.alloc_count)
            for i, elt in enumerate(val.elts):
                idx = base_types.VInt()
                idx.set_const_value(self.builder, i)
                target.o_subscript(idx, self.builder).set_value(self.builder,
                                                                elt)
        elif isinstance(node.value, ast.ListComp):
            if len(node.targets) > 1:
                raise NotImplementedError
            target = self.visit_expression(node.targets[0])
            target.set_count(self.builder, val.alloc_count)

            i = base_types.VInt()
            i.alloca(self.builder)
            i.auto_store(self.builder, ll.Constant(ll.IntType(32), 0))

            function = self.builder.basic_block.function
            copy_block = function.append_basic_block("ai_copy")
            end_block = function.append_basic_block("ai_end")
            self.builder.branch(copy_block)

            self.builder.position_at_end(copy_block)
            target.o_subscript(i, self.builder).set_value(self.builder,
                                                          val.elt)
            i.auto_store(self.builder, self.builder.add(
                i.auto_load(self.builder),
                ll.Constant(ll.IntType(32), 1)))
            cont = self.builder.icmp_signed(
                "<", i.auto_load(self.builder),
                ll.Constant(ll.IntType(32), val.alloc_count))
            self.builder.cbranch(cont, copy_block, end_block)

            self.builder.position_at_end(end_block)
        else:
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
        if not self._bb_terminated():
            self.builder.branch(merge_block)

        self.builder.position_at_end(else_block)
        self.visit_statements(node.orelse)
        if not self._bb_terminated():
            self.builder.branch(merge_block)

        self.builder.position_at_end(merge_block)

    def _enter_loop_body(self, break_block, continue_block):
        self._break_stack.append(break_block)
        self._continue_stack.append(continue_block)
        self._exception_level_stack.append(0)

    def _leave_loop_body(self):
        self._exception_level_stack.pop()
        self._continue_stack.pop()
        self._break_stack.pop()

    def _visit_stmt_While(self, node):
        function = self.builder.basic_block.function

        body_block = function.append_basic_block("w_body")
        else_block = function.append_basic_block("w_else")
        condition = self.visit_expression(node.test).o_bool(self.builder)
        self.builder.cbranch(
            condition.auto_load(self.builder), body_block, else_block)

        continue_block = function.append_basic_block("w_continue")
        merge_block = function.append_basic_block("w_merge")
        self.builder.position_at_end(body_block)
        self._enter_loop_body(merge_block, continue_block)
        self.visit_statements(node.body)
        self._leave_loop_body()
        if not self._bb_terminated():
            self.builder.branch(continue_block)

        self.builder.position_at_end(continue_block)
        condition = self.visit_expression(node.test).o_bool(self.builder)
        self.builder.cbranch(
            condition.auto_load(self.builder), body_block, merge_block)

        self.builder.position_at_end(else_block)
        self.visit_statements(node.orelse)
        if not self._bb_terminated():
            self.builder.branch(merge_block)

        self.builder.position_at_end(merge_block)

    def _visit_stmt_For(self, node):
        function = self.builder.basic_block.function

        it = self.visit_expression(node.iter)
        target = self.visit_expression(node.target)
        itval = it.get_value_ptr()

        body_block = function.append_basic_block("f_body")
        else_block = function.append_basic_block("f_else")
        cont = it.o_next(self.builder)
        self.builder.cbranch(
            cont.auto_load(self.builder), body_block, else_block)

        continue_block = function.append_basic_block("f_continue")
        merge_block = function.append_basic_block("f_merge")
        self.builder.position_at_end(body_block)
        target.set_value(self.builder, itval)
        self._enter_loop_body(merge_block, continue_block)
        self.visit_statements(node.body)
        self._leave_loop_body()
        if not self._bb_terminated():
            self.builder.branch(continue_block)

        self.builder.position_at_end(continue_block)
        cont = it.o_next(self.builder)
        self.builder.cbranch(
            cont.auto_load(self.builder), body_block, merge_block)

        self.builder.position_at_end(else_block)
        self.visit_statements(node.orelse)
        if not self._bb_terminated():
            self.builder.branch(merge_block)

        self.builder.position_at_end(merge_block)

    def _break_loop_body(self, target_block):
        exception_levels = self._exception_level_stack[-1]
        if exception_levels:
            self.runtime.build_pop(self.builder, exception_levels)
        self.builder.branch(target_block)

    def _visit_stmt_Break(self, node):
        self._break_loop_body(self._break_stack[-1])

    def _visit_stmt_Continue(self, node):
        self._break_loop_body(self._continue_stack[-1])

    def _visit_stmt_Return(self, node):
        if node.value is None:
            val = base_types.VNone()
        else:
            val = self.visit_expression(node.value)
        exception_levels = sum(self._exception_level_stack)
        if exception_levels:
            self.runtime.build_pop(self.builder, exception_levels)
        if isinstance(val, base_types.VNone):
            self.builder.ret_void()
        else:
            self.builder.ret(val.auto_load(self.builder))

    def _visit_stmt_Pass(self, node):
        pass

    def _visit_stmt_Raise(self, node):
        if self._active_exception_stack:
            finally_block, propagate, propagate_eid = (
                self._active_exception_stack[-1])
            self.builder.store(ll.Constant(ll.IntType(1), 1), propagate)
            if node.exc is not None:
                eid = ll.Constant(ll.IntType(32), node.exc.args[0].n)
                self.builder.store(eid, propagate_eid)
            self.builder.branch(finally_block)
        else:
            eid = ll.Constant(ll.IntType(32), node.exc.args[0].n)
            self.runtime.build_raise(self.builder, eid)

    def _handle_exception(self, function, finally_block,
                          propagate, propagate_eid, handlers):
        eid = self.runtime.build_getid(self.builder)
        self._active_exception_stack.append(
            (finally_block, propagate, propagate_eid))
        self.builder.store(ll.Constant(ll.IntType(1), 1), propagate)
        self.builder.store(eid, propagate_eid)

        for handler in handlers:
            handled_exc_block = function.append_basic_block("try_exc_h")
            cont_exc_block = function.append_basic_block("try_exc_c")
            if handler.type is None:
                self.builder.branch(handled_exc_block)
            else:
                if isinstance(handler.type, ast.Tuple):
                    match = self.builder.icmp_signed(
                        "==", eid,
                        ll.Constant(ll.IntType(32),
                                    handler.type.elts[0].args[0].n))
                    for elt in handler.type.elts[1:]:
                        match = self.builder.or_(
                            match,
                            self.builder.icmp_signed(
                                "==", eid,
                                ll.Constant(ll.IntType(32), elt.args[0].n)))
                else:
                    match = self.builder.icmp_signed(
                        "==", eid,
                        ll.Constant(ll.IntType(32), handler.type.args[0].n))
                self.builder.cbranch(match, handled_exc_block, cont_exc_block)
            self.builder.position_at_end(handled_exc_block)
            self.builder.store(ll.Constant(ll.IntType(1), 0), propagate)
            self.visit_statements(handler.body)
            if not self._bb_terminated():
                self.builder.branch(finally_block)
            self.builder.position_at_end(cont_exc_block)
        self.builder.branch(finally_block)

        self._active_exception_stack.pop()

    def _visit_stmt_Try(self, node):
        function = self.builder.basic_block.function
        noexc_block = function.append_basic_block("try_noexc")
        exc_block = function.append_basic_block("try_exc")
        finally_block = function.append_basic_block("try_finally")

        propagate = self.builder.alloca(ll.IntType(1),
                                        name="propagate")
        self.builder.store(ll.Constant(ll.IntType(1), 0), propagate)
        propagate_eid = self.builder.alloca(ll.IntType(32),
                                            name="propagate_eid")
        exception_occured = self.runtime.build_catch(self.builder)
        self.builder.cbranch(exception_occured, exc_block, noexc_block)

        self.builder.position_at_end(noexc_block)
        self._exception_level_stack[-1] += 1
        self.visit_statements(node.body)
        self._exception_level_stack[-1] -= 1
        if not self._bb_terminated():
            self.runtime.build_pop(self.builder, 1)
            self.visit_statements(node.orelse)
            if not self._bb_terminated():
                self.builder.branch(finally_block)
        self.builder.position_at_end(exc_block)
        self._handle_exception(function, finally_block,
                               propagate, propagate_eid, node.handlers)

        propagate_block = function.append_basic_block("try_propagate")
        merge_block = function.append_basic_block("try_merge")
        self.builder.position_at_end(finally_block)
        self.visit_statements(node.finalbody)
        if not self._bb_terminated():
            self.builder.cbranch(
                self.builder.load(propagate),
                propagate_block, merge_block)
        self.builder.position_at_end(propagate_block)
        self.runtime.build_raise(self.builder, self.builder.load(propagate_eid))
        self.builder.branch(merge_block)
        self.builder.position_at_end(merge_block)
