"""
:class:`IODelayEstimator` calculates the amount of time
elapsed from the point of view of the RTIO core for
every function.
"""

from pythonparser import ast, algorithm, diagnostic
from .. import types, iodelay, builtins, asttyped

class _UnknownDelay(Exception):
    pass

class _IndeterminateDelay(Exception):
    def __init__(self, cause):
        self.cause = cause

class IODelayEstimator(algorithm.Visitor):
    def __init__(self, engine, ref_period):
        self.engine         = engine
        self.ref_period     = ref_period
        self.changed        = False
        self.current_delay  = iodelay.Const(0)
        self.current_args   = None
        self.current_goto   = None
        self.current_return = None

    def evaluate(self, node, abort, context):
        if isinstance(node, asttyped.NumT):
            return iodelay.Const(node.n)
        elif isinstance(node, asttyped.CoerceT):
            return self.evaluate(node.value, abort, context)
        elif isinstance(node, asttyped.NameT):
            if self.current_args is None:
                note = diagnostic.Diagnostic("note",
                    "this variable is not an argument", {},
                    node.loc)
                abort([note])
            elif node.id in [arg.arg for arg in self.current_args.args]:
                return iodelay.Var(node.id)
            else:
                notes = [
                    diagnostic.Diagnostic("note",
                        "this variable is not an argument of the innermost function", {},
                        node.loc),
                    diagnostic.Diagnostic("note",
                        "only these arguments are in scope of analysis", {},
                        self.current_args.loc)
                ]
                abort(notes)
        elif isinstance(node, asttyped.BinOpT):
            lhs = self.evaluate(node.left, abort, context)
            rhs = self.evaluate(node.right, abort, context)
            if isinstance(node.op, ast.Add):
                return lhs + rhs
            elif isinstance(node.op, ast.Sub):
                return lhs - rhs
            elif isinstance(node.op, ast.Mult):
                return lhs * rhs
            elif isinstance(node.op, ast.Div):
                return lhs / rhs
            elif isinstance(node.op, ast.FloorDiv):
                return lhs // rhs
            else:
                note = diagnostic.Diagnostic("note",
                    "this operator is not supported {context}",
                    {"context": context},
                    node.op.loc)
                abort([note])
        else:
            note = diagnostic.Diagnostic("note",
                "this expression is not supported {context}",
                {"context": context},
                node.loc)
            abort([note])

    def abort(self, message, loc, notes=[]):
        diag = diagnostic.Diagnostic("error", message, {}, loc, notes=notes)
        raise _IndeterminateDelay(diag)

    def visit_fixpoint(self, node):
        while True:
            self.changed = False
            self.visit(node)
            if not self.changed:
                return

    def visit_ModuleT(self, node):
        try:
            for stmt in node.body:
                try:
                    self.visit(stmt)
                except _UnknownDelay:
                    pass # more luck next time?
        except _IndeterminateDelay:
            pass # we don't care; module-level code is never interleaved

    def visit_function(self, args, body, typ, loc):
        old_args, self.current_args = self.current_args, args
        old_return, self.current_return = self.current_return, None
        old_delay, self.current_delay = self.current_delay, iodelay.Const(0)
        try:
            self.visit(body)
            if not iodelay.is_zero(self.current_delay) and self.current_return is not None:
                self.abort("only return statement at the end of the function "
                           "can be interleaved", self.current_return.loc)

            delay = types.TFixedDelay(self.current_delay.fold())
        except _IndeterminateDelay as error:
            delay = types.TIndeterminateDelay(error.cause)
        self.current_delay = old_delay
        self.current_return = old_return
        self.current_args = old_args

        if types.is_indeterminate_delay(delay) and types.is_indeterminate_delay(typ.delay):
            # Both delays indeterminate; no point in unifying since that will
            # replace the lazy and more specific error with an eager and more generic
            # error (unification error of delay(?) with delay(?), which is useless).
            return

        try:
            old_delay = typ.delay.find()
            typ.delay.unify(delay)
            if typ.delay.find() != old_delay:
                self.changed = True
        except types.UnificationError as e:
            printer = types.TypePrinter()
            diag = diagnostic.Diagnostic("fatal",
                "delay {delaya} was inferred for this function, but its delay is already "
                "constrained externally to {delayb}",
                {"delaya": printer.name(delay), "delayb": printer.name(typ.delay)},
                loc)
            self.engine.process(diag)

    def visit_FunctionDefT(self, node):
        self.visit(node.args.defaults)
        self.visit(node.args.kw_defaults)

        # We can only handle return in tail position.
        if isinstance(node.body[-1], ast.Return):
            body = node.body[:-1]
        else:
            body = node.body
        self.visit_function(node.args, body, node.signature_type.find(), node.loc)

    visit_QuotedFunctionDefT = visit_FunctionDefT

    def visit_LambdaT(self, node):
        self.visit_function(node.args, node.body, node.type.find(), node.loc)

    def get_iterable_length(self, node, context):
        def abort(notes):
            self.abort("for statement cannot be interleaved because "
                       "iteration count is indeterminate",
                       node.loc, notes)

        def evaluate(node):
            return self.evaluate(node, abort, context)

        if isinstance(node, asttyped.CallT) and types.is_builtin(node.func.type, "range"):
            range_min, range_max, range_step = iodelay.Const(0), None, iodelay.Const(1)
            if len(node.args) == 3:
                range_min, range_max, range_step = map(evaluate, node.args)
            elif len(node.args) == 2:
                range_min, range_max = map(evaluate, node.args)
            elif len(node.args) == 1:
                range_max, = map(evaluate, node.args)
            return (range_max - range_min) // range_step
        else:
            note = diagnostic.Diagnostic("note",
                "this value is not a constant range literal", {},
                node.loc)
            abort([note])

    def visit_ForT(self, node):
        self.visit(node.iter)

        old_goto, self.current_goto = self.current_goto, None
        old_delay, self.current_delay = self.current_delay, iodelay.Const(0)
        self.visit(node.body)
        if iodelay.is_zero(self.current_delay):
            self.current_delay = old_delay
        else:
            if self.current_goto is not None:
                self.abort("loop iteration count is indeterminate because of control flow",
                           self.current_goto.loc)

            context            = "in an iterable used in a for loop that is being interleaved"
            node.trip_count    = self.get_iterable_length(node.iter, context).fold()
            node.trip_interval = self.current_delay.fold()
            self.current_delay = old_delay + node.trip_interval * node.trip_count
        self.current_goto = old_goto

        self.visit(node.orelse)

    def visit_goto(self, node):
        self.current_goto = node

    visit_Break    = visit_goto
    visit_Continue = visit_goto

    def visit_control_flow(self, kind, node):
        old_delay, self.current_delay = self.current_delay, iodelay.Const(0)
        self.generic_visit(node)
        if not iodelay.is_zero(self.current_delay):
            self.abort("{} cannot be interleaved".format(kind), node.loc)
        self.current_delay = old_delay

    visit_If     = lambda self, node: self.visit_control_flow("if statement",    node)
    visit_IfExpT = lambda self, node: self.visit_control_flow("if expression",   node)
    visit_Try    = lambda self, node: self.visit_control_flow("try statement",   node)

    def visit_While(self, node):
        old_goto, self.current_goto = self.current_goto, None
        self.visit_control_flow("while statement", node)
        self.current_goto = old_goto

    def visit_Return(self, node):
        self.current_return = node

    def visit_With(self, node):
        self.visit(node.items)

        context_expr = node.items[0].context_expr
        if len(node.items) == 1 and types.is_builtin(context_expr.type, "interleave"):
            try:
                delays = []
                for stmt in node.body:
                    old_delay, self.current_delay = self.current_delay, iodelay.Const(0)
                    self.visit(stmt)
                    delays.append(self.current_delay)
                    self.current_delay = old_delay

                if any(delays):
                    self.current_delay += iodelay.Max(delays)
            except _IndeterminateDelay as error:
                # Interleave failures inside `with` statements are hard failures,
                # since there's no chance that the code will never actually execute
                # inside a `with` statement after all.
                note = diagnostic.Diagnostic("note",
                    "while interleaving this 'with interleave:' statement", {},
                    node.loc)
                error.cause.notes += [note]
                self.engine.process(error.cause)

            flow_stmt = None
            if self.current_goto is not None:
                flow_stmt = self.current_goto
            elif self.current_return is not None:
                flow_stmt = self.current_return

            if flow_stmt is not None:
                note = diagnostic.Diagnostic("note",
                    "this '{kind}' statement transfers control out of "
                    "the 'with interleave:' statement",
                    {"kind": flow_stmt.keyword_loc.source()},
                    flow_stmt.loc)
                diag = diagnostic.Diagnostic("error",
                    "cannot interleave this 'with interleave:' statement", {},
                    node.keyword_loc.join(node.colon_loc), notes=[note])
                self.engine.process(diag)

        elif len(node.items) == 1 and types.is_builtin(context_expr.type, "sequential"):
            self.visit(node.body)
        else:
            self.abort("with statement cannot be interleaved", node.loc)

    def visit_CallT(self, node):
        typ = node.func.type.find()
        def abort(notes):
            self.abort("call cannot be interleaved because "
                       "an argument cannot be statically evaluated",
                       node.loc, notes)

        if types.is_builtin(typ, "delay"):
            value = self.evaluate(node.args[0], abort=abort,
                                  context="as an argument for delay()")
            call_delay = iodelay.SToMU(value, ref_period=self.ref_period)
        elif types.is_builtin(typ, "delay_mu"):
            value = self.evaluate(node.args[0], abort=abort,
                                  context="as an argument for delay_mu()")
            call_delay = value
        elif not types.is_builtin(typ):
            if types.is_function(typ) or types.is_rpc(typ):
                offset = 0
            elif types.is_method(typ):
                offset = 1
                typ = types.get_method_function(typ)
            else:
                assert False

            if types.is_rpc(typ):
                call_delay = iodelay.Const(0)
            else:
                delay = typ.find().delay.find()
                if types.is_var(delay):
                    raise _UnknownDelay()
                elif delay.is_indeterminate():
                    note = diagnostic.Diagnostic("note",
                        "function called here", {},
                        node.loc)
                    cause = delay.cause
                    cause = diagnostic.Diagnostic(cause.level, cause.reason, cause.arguments,
                                                  cause.location, cause.highlights,
                                                  cause.notes + [note])
                    raise _IndeterminateDelay(cause)
                elif delay.is_fixed():
                    args = {}
                    for kw_node in node.keywords:
                        args[kw_node.arg] = kw_node.value
                    for arg_name, arg_node in zip(list(typ.args)[offset:], node.args):
                        args[arg_name] = arg_node

                    free_vars = delay.duration.free_vars()
                    node.arg_exprs = {
                        arg: self.evaluate(args[arg], abort=abort,
                                           context="in the expression for argument '{}' "
                                                   "that affects I/O delay".format(arg))
                        for arg in free_vars
                    }
                    call_delay = delay.duration.fold(node.arg_exprs)
                else:
                    assert False
        else:
            call_delay = iodelay.Const(0)

        self.current_delay += call_delay
        node.iodelay = call_delay
