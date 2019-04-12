"""
:class:`ARTIQIRGenerator` transforms typed AST into ARTIQ intermediate
representation. ARTIQ IR is designed to be low-level enough that
its operations are elementary--contain no internal branching--
but without too much detail, such as exposing the reference/value
semantics explicitly.
"""

from collections import OrderedDict, defaultdict
from pythonparser import algorithm, diagnostic, ast
from .. import types, builtins, asttyped, ir, iodelay

def _readable_name(insn):
    if isinstance(insn, ir.Constant):
        return str(insn.value)
    else:
        return insn.name

def _extract_loc(node):
    if "keyword_loc" in node._locs:
        return node.keyword_loc
    else:
        return node.loc

# We put some effort in keeping generated IR readable,
# i.e. with a more or less linear correspondence to the source.
# This is why basic blocks sometimes seem to be produced in an odd order.
class ARTIQIRGenerator(algorithm.Visitor):
    """
    :class:`ARTIQIRGenerator` contains a lot of internal state,
    which is effectively maintained in a stack--with push/pop
    pairs around any state updates. It is comprised of following:

    :ivar current_loc: (:class:`pythonparser.source.Range`)
        source range of the node being currently visited
    :ivar current_function: (:class:`ir.Function` or None)
        module, def or lambda currently being translated
    :ivar current_globals: (set of string)
        set of variables that will be resolved in global scope
    :ivar current_block: (:class:`ir.BasicBlock`)
        basic block to which any new instruction will be appended
    :ivar current_env: (:class:`ir.Alloc` of type :class:`ir.TEnvironment`)
        the chained function environment, containing variables that
        can become upvalues
    :ivar current_private_env: (:class:`ir.Alloc` of type :class:`ir.TEnvironment`)
        the private function environment, containing internal state
    :ivar current_args: (dict of string to :class:`ir.Argument`)
        the map of Python names of formal arguments to
        the current function to their SSA names
    :ivar current_assign: (:class:`ir.Value` or None)
        the right-hand side of current assignment statement, or
        a component of a composite right-hand side when visiting
        a composite left-hand side, such as, in ``x, y = z``,
        the 2nd tuple element when visting ``y``
    :ivar current_assert_env: (:class:`ir.Alloc` of type :class:`ir.TEnvironment`)
        the environment where the individual components of current assert
        statement are stored until display
    :ivar current_assert_subexprs: (list of (:class:`ast.AST`, string))
        the mapping from components of current assert statement to the names
        their values have in :ivar:`current_assert_env`
    :ivar break_target: (:class:`ir.BasicBlock` or None)
        the basic block to which ``break`` will transfer control
    :ivar continue_target: (:class:`ir.BasicBlock` or None)
        the basic block to which ``continue`` will transfer control
    :ivar return_target: (:class:`ir.BasicBlock` or None)
        the basic block to which ``return`` will transfer control
    :ivar unwind_target: (:class:`ir.BasicBlock` or None)
        the basic block to which unwinding will transfer control
    :ivar final_branch: (function (target: :class:`ir.BasicBlock`, block: :class:`ir.BasicBlock)
                         or None)
        the function that appends to ``block`` a jump through the ``finally`` statement
        to ``target``

    There is, additionally, some global state that is used to translate
    the results of analyses on AST level to IR level:

    :ivar function_map: (map of :class:`ast.FunctionDefT` to :class:`ir.Function`)
        the map from function definition nodes to IR functions
    :ivar variable_map: (map of :class:`ast.NameT` to :class:`ir.GetLocal`)
        the map from variable name nodes to instructions retrieving
        the variable values
    :ivar method_map: (map of :class:`ast.AttributeT` to :class:`ir.GetAttribute`)
        the map from method resolution nodes to instructions retrieving
        the called function inside a translated :class:`ast.CallT` node
    """

    _size_type = builtins.TInt32()

    def __init__(self, module_name, engine, ref_period):
        self.engine = engine
        self.functions = []
        self.name = [module_name] if module_name != "" else []
        self.ref_period = ir.Constant(ref_period, builtins.TFloat())
        self.current_loc = None
        self.current_function = None
        self.current_class = None
        self.current_globals = set()
        self.current_block = None
        self.current_env = None
        self.current_private_env = None
        self.current_args = None
        self.current_assign = None
        self.current_assert_env = None
        self.current_assert_subexprs = None
        self.break_target = None
        self.continue_target = None
        self.return_target = None
        self.unwind_target = None
        self.final_branch = None
        self.function_map = dict()
        self.variable_map = dict()
        self.method_map = defaultdict(lambda: [])

    def annotate_calls(self, devirtualization):
        for var_node in devirtualization.variable_map:
            callee_node = devirtualization.variable_map[var_node]
            if callee_node is None:
                continue
            callee = self.function_map[callee_node]

            call_target = self.variable_map[var_node]
            for use in call_target.uses:
                if isinstance(use, (ir.Call, ir.Invoke)) and \
                        use.target_function() == call_target:
                    use.static_target_function = callee

        for type_and_method in devirtualization.method_map:
            callee_node = devirtualization.method_map[type_and_method]
            if callee_node is None:
                continue
            callee = self.function_map[callee_node]

            for call in self.method_map[type_and_method]:
                assert isinstance(call, (ir.Call, ir.Invoke))
                call.static_target_function = callee

    def add_block(self, name=""):
        block = ir.BasicBlock([], name)
        self.current_function.add(block)
        return block

    def append(self, insn, block=None, loc=None):
        if loc is None:
            loc = self.current_loc
        if block is None:
            block = self.current_block

        if insn.loc is None:
            insn.loc = loc
        return block.append(insn)

    def terminate(self, insn):
        if not self.current_block.is_terminated():
            self.append(insn)
        else:
            insn.drop_references()

    def warn_unreachable(self, node):
        diag = diagnostic.Diagnostic("warning",
            "unreachable code", {},
            node.loc.begin())
        self.engine.process(diag)

    # Visitors

    def visit(self, obj):
        if isinstance(obj, list):
            for elt in obj:
                if self.current_block.is_terminated():
                    self.warn_unreachable(elt)
                    break
                self.visit(elt)
        elif isinstance(obj, ast.AST):
            try:
                old_loc, self.current_loc = self.current_loc, _extract_loc(obj)
                return self._visit_one(obj)
            finally:
                self.current_loc = old_loc

    # Module visitor

    def visit_ModuleT(self, node):
        # Treat start of module as synthesized
        self.current_loc = None

        try:
            typ = types.TFunction(OrderedDict(), OrderedDict(), builtins.TNone())
            func = ir.Function(typ, ".".join(self.name + ['__modinit__']), [],
                               loc=node.loc.begin())
            self.functions.append(func)
            old_func, self.current_function = self.current_function, func

            entry = self.add_block("entry")
            old_block, self.current_block = self.current_block, entry

            env_type = ir.TEnvironment(name=func.name, vars=node.typing_env)
            env = self.append(ir.Alloc([], env_type, name="env"))
            old_env, self.current_env = self.current_env, env

            priv_env_type = ir.TEnvironment(name=func.name + ".priv", vars={ "$return": typ.ret })
            priv_env = self.append(ir.Alloc([], priv_env_type, name="privenv"))
            old_priv_env, self.current_private_env = self.current_private_env, priv_env

            self.generic_visit(node)
            self.terminate(ir.Return(ir.Constant(None, builtins.TNone())))

            return self.functions
        finally:
            self.current_function = old_func
            self.current_block = old_block
            self.current_env = old_env
            self.current_private_env = old_priv_env

    # Statement visitors

    def visit_ClassDefT(self, node):
        klass = self.append(ir.Alloc([], node.constructor_type,
                                     name="class.{}".format(node.name)))
        self._set_local(node.name, klass)

        try:
            old_class, self.current_class = self.current_class, klass
            self.visit(node.body)
        finally:
            self.current_class = old_class

    def visit_function(self, node, is_lambda=False, is_internal=False, is_quoted=False,
                       flags={}):
        if is_lambda:
            name = "lambda@{}:{}".format(node.loc.line(), node.loc.column())
            typ = node.type.find()
        else:
            name = node.name
            typ = node.signature_type.find()

        try:
            defaults = []
            if not is_quoted:
                for arg_name, default_node in zip(typ.optargs, node.args.defaults):
                    default = self.visit(default_node)
                    env_default_name = \
                        self.current_env.type.add("$default." + arg_name, default.type)
                    self.append(ir.SetLocal(self.current_env, env_default_name, default))
                    def codegen_default(env_default_name):
                        return lambda: self.append(ir.GetLocal(self.current_env, env_default_name))
                    defaults.append(codegen_default(env_default_name))
            else:
                for default_node in node.args.defaults:
                    def codegen_default(default_node):
                        return lambda: self.visit(default_node)
                    defaults.append(codegen_default(default_node))

            old_name, self.name = self.name, self.name + [name]

            env_arg  = ir.EnvironmentArgument(self.current_env.type, "ARG.ENV")

            old_args, self.current_args = self.current_args, {}

            args = []
            for arg_name in typ.args:
                arg = ir.Argument(typ.args[arg_name], "ARG." + arg_name)
                self.current_args[arg_name] = arg
                args.append(arg)

            optargs = []
            for arg_name in typ.optargs:
                arg = ir.Argument(ir.TOption(typ.optargs[arg_name]), "ARG." + arg_name)
                self.current_args[arg_name] = arg
                optargs.append(arg)

            for (arg, arg_node) in zip(args + optargs, node.args.args):
                arg.loc = arg_node.loc

            func = ir.Function(typ, ".".join(self.name), [env_arg] + args + optargs,
                               loc=node.lambda_loc if is_lambda else node.keyword_loc)
            func.is_internal = is_internal
            func.flags = flags
            self.functions.append(func)
            old_func, self.current_function = self.current_function, func

            if not is_lambda:
                self.function_map[node] = func

            entry = self.add_block("entry")
            old_block, self.current_block = self.current_block, entry

            old_globals, self.current_globals = self.current_globals, node.globals_in_scope

            env_without_globals = \
                {var: node.typing_env[var]
                 for var in node.typing_env
                  if var not in node.globals_in_scope}
            env_type = ir.TEnvironment(name=func.name,
                                       vars=env_without_globals, outer=self.current_env.type)
            env = self.append(ir.Alloc([], env_type, name="ENV"))
            old_env, self.current_env = self.current_env, env

            if not is_lambda:
                priv_env_type = ir.TEnvironment(name="{}.private".format(func.name),
                                                vars={ "$return": typ.ret })
                priv_env = self.append(ir.Alloc([], priv_env_type, name="PRV"))
                old_priv_env, self.current_private_env = self.current_private_env, priv_env

            self.append(ir.SetLocal(env, "$outer", env_arg))
            for index, arg_name in enumerate(typ.args):
                self.append(ir.SetLocal(env, arg_name, args[index]))
            for index, (arg_name, codegen_default) in enumerate(zip(typ.optargs, defaults)):
                default = codegen_default()
                value = self.append(ir.Builtin("unwrap_or", [optargs[index], default],
                                               typ.optargs[arg_name],
                                               name="DEF.{}".format(arg_name)))
                self.append(ir.SetLocal(env, arg_name, value))

            result = self.visit(node.body)

            if is_lambda:
                self.terminate(ir.Return(result))
            elif builtins.is_none(typ.ret):
                if not self.current_block.is_terminated():
                    self.current_block.append(ir.Return(ir.Constant(None, builtins.TNone())))
            else:
                if not self.current_block.is_terminated():
                    if len(self.current_block.predecessors()) != 0:
                        diag = diagnostic.Diagnostic("error",
                            "this function must return a value of type {typ} explicitly",
                            {"typ": types.TypePrinter().name(typ.ret)},
                            node.keyword_loc)
                        self.engine.process(diag)

                    self.current_block.append(ir.Unreachable())

        finally:
            self.name = old_name
            self.current_args = old_args
            self.current_function = old_func
            self.current_block = old_block
            self.current_globals = old_globals
            self.current_env = old_env
            if not is_lambda:
                self.current_private_env = old_priv_env

        return self.append(ir.Closure(func, self.current_env))

    def visit_FunctionDefT(self, node):
        func = self.visit_function(node, is_internal=len(self.name) > 0)
        if self.current_class is None:
            self._set_local(node.name, func)
        else:
            self.append(ir.SetAttr(self.current_class, node.name, func))

    def visit_QuotedFunctionDefT(self, node):
        self.visit_function(node, is_internal=True, is_quoted=True, flags=node.flags)

    def visit_Return(self, node):
        if node.value is None:
            return_value = ir.Constant(None, builtins.TNone())
        else:
            return_value = self.visit(node.value)

        if self.return_target is None:
            self.append(ir.Return(return_value))
        else:
            self.append(ir.SetLocal(self.current_private_env, "$return", return_value))
            self.append(ir.Branch(self.return_target))

    def visit_Expr(self, node):
        # Ignore the value, do it for side effects.
        result = self.visit(node.value)

        # See comment in visit_Pass.
        if isinstance(result, ir.Constant):
            self.visit_Pass(node)

    def visit_Pass(self, node):
        # Insert a dummy instruction so that analyses which extract
        # locations from CFG have something to use.
        self.append(ir.Builtin("nop", [], builtins.TNone()))

    def visit_Assign(self, node):
        try:
            self.current_assign = self.visit(node.value)
            assert self.current_assign is not None
            for target in node.targets:
                self.visit(target)
        finally:
            self.current_assign = None

    def visit_AugAssign(self, node):
        lhs = self.visit(node.target)
        rhs = self.visit(node.value)
        value = self.append(ir.Arith(node.op, lhs, rhs))
        try:
            self.current_assign = value
            self.visit(node.target)
        finally:
            self.current_assign = None

    def coerce_to_bool(self, insn, block=None):
        if builtins.is_bool(insn.type):
            return insn
        elif builtins.is_int(insn.type):
            return self.append(ir.Compare(ast.NotEq(loc=None), insn, ir.Constant(0, insn.type)),
                               block=block)
        elif builtins.is_float(insn.type):
            return self.append(ir.Compare(ast.NotEq(loc=None), insn, ir.Constant(0, insn.type)),
                               block=block)
        elif builtins.is_iterable(insn.type):
            length = self.iterable_len(insn)
            return self.append(ir.Compare(ast.NotEq(loc=None), length, ir.Constant(0, length.type)),
                               block=block)
        else:
            note = diagnostic.Diagnostic("note",
                "this expression has type {type}",
                {"type": types.TypePrinter().name(insn.type)},
                insn.loc)
            diag = diagnostic.Diagnostic("warning",
                "this expression, which is always truthful, is coerced to bool", {},
                insn.loc, notes=[note])
            self.engine.process(diag)
            return ir.Constant(True, builtins.TBool())

    def visit_If(self, node):
        cond = self.visit(node.test)
        cond = self.coerce_to_bool(cond)
        head = self.current_block

        if_true = self.add_block("if.body")
        self.current_block = if_true
        self.visit(node.body)
        post_if_true = self.current_block

        if any(node.orelse):
            if_false = self.add_block("if.else")
            self.current_block = if_false
            self.visit(node.orelse)
            post_if_false = self.current_block

        tail = self.add_block("if.tail")
        self.current_block = tail
        if not post_if_true.is_terminated():
            post_if_true.append(ir.Branch(tail))

        if any(node.orelse):
            if not post_if_false.is_terminated():
                post_if_false.append(ir.Branch(tail))
            self.append(ir.BranchIf(cond, if_true, if_false), block=head)
        else:
            self.append(ir.BranchIf(cond, if_true, tail), block=head)

    def visit_While(self, node):
        try:
            head = self.add_block("while.head")
            self.append(ir.Branch(head))
            self.current_block = head
            old_continue, self.continue_target = self.continue_target, head
            cond = self.visit(node.test)
            cond = self.coerce_to_bool(cond)
            post_head = self.current_block

            break_block = self.add_block("while.break")
            old_break, self.break_target = self.break_target, break_block

            body = self.add_block("while.body")
            self.current_block = body
            self.visit(node.body)
            post_body = self.current_block
        finally:
            self.break_target = old_break
            self.continue_target = old_continue

        if any(node.orelse):
            else_tail = self.add_block("while.else")
            self.current_block = else_tail
            self.visit(node.orelse)
            post_else_tail = self.current_block

        tail = self.add_block("while.tail")
        self.current_block = tail

        if any(node.orelse):
            if not post_else_tail.is_terminated():
                post_else_tail.append(ir.Branch(tail))
        else:
            else_tail = tail

        post_head.append(ir.BranchIf(cond, body, else_tail))
        if not post_body.is_terminated():
            post_body.append(ir.Branch(head))
        break_block.append(ir.Branch(tail))

    def iterable_len(self, value, typ=_size_type):
        if builtins.is_listish(value.type):
            if isinstance(value, ir.Constant):
                name = None
            else:
                name = "{}.len".format(value.name)
            len = self.append(ir.Builtin("len", [value], builtins.TInt32(),
                                         name=name))
            return self.append(ir.Coerce(len, typ))
        elif builtins.is_range(value.type):
            start  = self.append(ir.GetAttr(value, "start"))
            stop   = self.append(ir.GetAttr(value, "stop"))
            step   = self.append(ir.GetAttr(value, "step"))
            spread = self.append(ir.Arith(ast.Sub(loc=None), stop, start))
            return self.append(ir.Arith(ast.FloorDiv(loc=None), spread, step,
                                        name="{}.len".format(value.name)))
        else:
            assert False

    def iterable_get(self, value, index):
        # Assuming the value is within bounds.
        if builtins.is_listish(value.type):
            return self.append(ir.GetElem(value, index))
        elif builtins.is_range(value.type):
            start  = self.append(ir.GetAttr(value, "start"))
            step   = self.append(ir.GetAttr(value, "step"))
            offset = self.append(ir.Arith(ast.Mult(loc=None), step, index))
            return self.append(ir.Arith(ast.Add(loc=None), start, offset))
        else:
            assert False

    def visit_ForT(self, node):
        try:
            iterable = self.visit(node.iter)
            length = self.iterable_len(iterable)
            prehead = self.current_block

            head = self.add_block("for.head")
            self.append(ir.Branch(head))
            self.current_block = head
            phi = self.append(ir.Phi(length.type, name="IND"))
            phi.add_incoming(ir.Constant(0, phi.type), prehead)
            cond = self.append(ir.Compare(ast.Lt(loc=None), phi, length, name="CMP"))

            break_block = self.add_block("for.break")
            old_break, self.break_target = self.break_target, break_block

            continue_block = self.add_block("for.continue")
            old_continue, self.continue_target = self.continue_target, continue_block
            self.current_block = continue_block

            updated_index = self.append(ir.Arith(ast.Add(loc=None), phi, ir.Constant(1, phi.type),
                                                 name="IND.new"))
            phi.add_incoming(updated_index, continue_block)
            self.append(ir.Branch(head))

            body = self.add_block("for.body")
            self.current_block = body
            elt = self.iterable_get(iterable, phi)
            try:
                self.current_assign = elt
                self.visit(node.target)
            finally:
                self.current_assign = None
            self.visit(node.body)
            post_body = self.current_block
        finally:
            self.break_target = old_break
            self.continue_target = old_continue

        if any(node.orelse):
            else_tail = self.add_block("for.else")
            self.current_block = else_tail
            self.visit(node.orelse)
            post_else_tail = self.current_block

        tail = self.add_block("for.tail")
        self.current_block = tail

        if any(node.orelse):
            if not post_else_tail.is_terminated():
                post_else_tail.append(ir.Branch(tail))
        else:
            else_tail = tail

        if node.trip_count is not None:
            head.append(ir.Loop(node.trip_count, phi, cond, body, else_tail))
        else:
            head.append(ir.BranchIf(cond, body, else_tail))
        if not post_body.is_terminated():
            post_body.append(ir.Branch(continue_block))
        break_block.append(ir.Branch(tail))

    def visit_Break(self, node):
        self.append(ir.Branch(self.break_target))

    def visit_Continue(self, node):
        self.append(ir.Branch(self.continue_target))

    def raise_exn(self, exn=None, loc=None):
        if self.final_branch is not None:
            raise_proxy = self.add_block("try.raise")
            self.final_branch(raise_proxy, self.current_block)
            self.current_block = raise_proxy

        if exn is not None:
            assert loc is not None
            loc_file = ir.Constant(loc.source_buffer.name, builtins.TStr())
            loc_line = ir.Constant(loc.line(), builtins.TInt32())
            loc_column = ir.Constant(loc.column(), builtins.TInt32())
            loc_function = ir.Constant(".".join(self.name), builtins.TStr())

            self.append(ir.SetAttr(exn, "__file__", loc_file))
            self.append(ir.SetAttr(exn, "__line__", loc_line))
            self.append(ir.SetAttr(exn, "__col__", loc_column))
            self.append(ir.SetAttr(exn, "__func__", loc_function))

            if self.unwind_target is not None:
                self.append(ir.Raise(exn, self.unwind_target))
            else:
                self.append(ir.Raise(exn))
        else:
            if self.unwind_target is not None:
                self.append(ir.Reraise(self.unwind_target))
            else:
                self.append(ir.Reraise())

    def visit_Raise(self, node):
        if node.exc is not None and types.is_exn_constructor(node.exc.type):
            self.raise_exn(self.alloc_exn(node.exc.type.instance), loc=self.current_loc)
        else:
            self.raise_exn(self.visit(node.exc), loc=self.current_loc)

    def visit_Try(self, node):
        dispatcher = self.add_block("try.dispatch")

        if any(node.finalbody):
            # k for continuation
            final_suffix   = ".try@{}:{}".format(node.loc.line(), node.loc.column())
            final_env_type = ir.TEnvironment(name=self.current_function.name + final_suffix,
                                             vars={ "$cont": ir.TBasicBlock() })
            final_state    = self.append(ir.Alloc([], final_env_type))
            final_targets  = []
            final_paths    = []

            def final_branch(target, block):
                block.append(ir.SetLocal(final_state, "$cont", target))
                final_targets.append(target)
                final_paths.append(block)

            if self.break_target is not None:
                break_proxy = self.add_block("try.break")
                old_break, self.break_target = self.break_target, break_proxy
                final_branch(old_break, break_proxy)

            if self.continue_target is not None:
                continue_proxy = self.add_block("try.continue")
                old_continue, self.continue_target = self.continue_target, continue_proxy
                final_branch(old_continue, continue_proxy)

            return_proxy = self.add_block("try.return")
            old_return, self.return_target = self.return_target, return_proxy
            if old_return is not None:
                final_branch(old_return, return_proxy)
            else:
                return_action = self.add_block("try.doreturn")
                value = return_action.append(ir.GetLocal(self.current_private_env, "$return"))
                return_action.append(ir.Return(value))
                final_branch(return_action, return_proxy)

        body = self.add_block("try.body")
        self.append(ir.Branch(body))
        self.current_block = body

        try:
            old_unwind, self.unwind_target = self.unwind_target, dispatcher
            self.visit(node.body)
        finally:
            self.unwind_target = old_unwind

        if not self.current_block.is_terminated():
            self.visit(node.orelse)
        elif any(node.orelse):
            self.warn_unreachable(node.orelse[0])
        body = self.current_block

        if any(node.finalbody):
            if self.break_target:
                self.break_target = old_break
            if self.continue_target:
                self.continue_target = old_continue
            self.return_target = old_return

            old_final_branch, self.final_branch = self.final_branch, final_branch

        cleanup = self.add_block('handler.cleanup')
        landingpad = dispatcher.append(ir.LandingPad(cleanup))

        handlers = []
        for handler_node in node.handlers:
            exn_type = handler_node.name_type.find()
            if handler_node.filter is not None and \
                    not builtins.is_exception(exn_type, 'Exception'):
                handler = self.add_block("handler." + exn_type.name)
                landingpad.add_clause(handler, exn_type)
            else:
                handler = self.add_block("handler.catchall")
                landingpad.add_clause(handler, None)

            self.current_block = handler
            if handler_node.name is not None:
                exn = self.append(ir.Builtin("exncast", [landingpad], handler_node.name_type))
                self._set_local(handler_node.name, exn)
            self.visit(handler_node.body)
            post_handler = self.current_block

            handlers.append((handler, post_handler))

        if any(node.finalbody):
            # Finalize and continue after try statement.
            self.final_branch = old_final_branch

            finalizer = self.add_block("finally")
            self.current_block = finalizer

            self.visit(node.finalbody)
            post_finalizer = self.current_block

            # Finalize and reraise. Separate from previous case to expose flow
            # to LocalAccessValidator.
            finalizer_reraise = self.add_block("finally.reraise")
            self.current_block = finalizer_reraise

            self.visit(node.finalbody)
            self.terminate(ir.Reraise(self.unwind_target))

        self.current_block = tail = self.add_block("try.tail")
        if any(node.finalbody):
            final_targets.append(tail)

            for block in final_paths:
                block.append(ir.Branch(finalizer))

            if not body.is_terminated():
                body.append(ir.SetLocal(final_state, "$cont", tail))
                body.append(ir.Branch(finalizer))

            cleanup.append(ir.Branch(finalizer_reraise))

            for handler, post_handler in handlers:
                if not post_handler.is_terminated():
                    post_handler.append(ir.SetLocal(final_state, "$cont", tail))
                    post_handler.append(ir.Branch(finalizer))

            if not post_finalizer.is_terminated():
                dest = post_finalizer.append(ir.GetLocal(final_state, "$cont"))
                post_finalizer.append(ir.IndirectBranch(dest, final_targets))
        else:
            if not body.is_terminated():
                body.append(ir.Branch(tail))

            cleanup.append(ir.Reraise(self.unwind_target))

            for handler, post_handler in handlers:
                if not post_handler.is_terminated():
                    post_handler.append(ir.Branch(tail))

    def _try_finally(self, body_gen, finally_gen, name):
        dispatcher = self.add_block("{}.dispatch".format(name))

        try:
            old_unwind, self.unwind_target = self.unwind_target, dispatcher
            body_gen()
        finally:
            self.unwind_target = old_unwind

        if not self.current_block.is_terminated():
            finally_gen()

        self.post_body = self.current_block

        self.current_block = self.add_block("{}.cleanup".format(name))
        dispatcher.append(ir.LandingPad(self.current_block))
        finally_gen()
        self.raise_exn()

        self.current_block = self.post_body

    def visit_With(self, node):
        context_expr_node  = node.items[0].context_expr
        optional_vars_node = node.items[0].optional_vars

        if types.is_builtin(context_expr_node.type, "sequential"):
            self.visit(node.body)
            return
        elif types.is_builtin(context_expr_node.type, "interleave"):
            interleave = self.append(ir.Interleave([]))

            heads, tails = [], []
            for stmt in node.body:
                self.current_block = self.add_block("interleave.branch")
                heads.append(self.current_block)
                self.visit(stmt)
                tails.append(self.current_block)

            for head in heads:
                interleave.add_destination(head)

            self.current_block = self.add_block("interleave.tail")
            for tail in tails:
                if not tail.is_terminated():
                    tail.append(ir.Branch(self.current_block))
            return
        elif types.is_builtin(context_expr_node.type, "parallel"):
            start_mu = self.append(ir.Builtin("now_mu", [], builtins.TInt64()))
            end_mu   = start_mu

            for stmt in node.body:
                self.append(ir.Builtin("at_mu", [start_mu], builtins.TNone()))

                block = self.add_block("parallel.branch")
                if self.current_block.is_terminated():
                    self.warn_unreachable(stmt[0])
                else:
                    self.append(ir.Branch(block))
                self.current_block = block

                self.visit(stmt)

                mid_mu = self.append(ir.Builtin("now_mu", [], builtins.TInt64()))
                gt_mu  = self.append(ir.Compare(ast.Gt(loc=None), mid_mu, end_mu))
                end_mu = self.append(ir.Select(gt_mu, mid_mu, end_mu))

            self.append(ir.Builtin("at_mu", [end_mu], builtins.TNone()))
            return

        cleanup = []
        for item_node in node.items:
            context_expr_node  = item_node.context_expr
            optional_vars_node = item_node.optional_vars

            if isinstance(context_expr_node, asttyped.CallT) and \
                    types.is_builtin(context_expr_node.func.type, "watchdog"):
                timeout        = self.visit(context_expr_node.args[0])
                timeout_ms     = self.append(ir.Arith(ast.Mult(loc=None), timeout,
                                                      ir.Constant(1000, builtins.TFloat())))
                timeout_ms_int = self.append(ir.Coerce(timeout_ms, builtins.TInt64()))

                watchdog_id = self.append(ir.Builtin("watchdog_set", [timeout_ms_int],
                                                     builtins.TInt32()))
                cleanup.append(lambda:
                    self.append(ir.Builtin("watchdog_clear", [watchdog_id], builtins.TNone())))
            else: # user-defined context manager
                context_mgr = self.visit(context_expr_node)
                enter_fn    = self.append(ir.GetAttr(context_mgr, '__enter__'))
                exit_fn     = self.append(ir.GetAttr(context_mgr, '__exit__'))

                try:
                    self.current_assign = self._user_call(enter_fn, [], {})
                    if optional_vars_node is not None:
                        self.visit(optional_vars_node)
                finally:
                    self.current_assign = None

                none = self.append(ir.Alloc([], builtins.TNone()))
                cleanup.append(lambda:
                    self._user_call(exit_fn, [none, none, none], {}))

        self._try_finally(
            body_gen=lambda: self.visit(node.body),
            finally_gen=lambda: [thunk() for thunk in cleanup],
            name="with")

    # Expression visitors
    # These visitors return a node in addition to mutating
    # the IR.

    def visit_LambdaT(self, node):
        return self.visit_function(node, is_lambda=True, is_internal=True)

    def visit_IfExpT(self, node):
        cond = self.visit(node.test)
        head = self.current_block

        if_true = self.add_block("ifexp.body")
        self.current_block = if_true
        true_result = self.visit(node.body)
        post_if_true = self.current_block

        if_false = self.add_block("ifexp.else")
        self.current_block = if_false
        false_result = self.visit(node.orelse)
        post_if_false = self.current_block

        tail = self.add_block("ifexp.tail")
        self.current_block = tail

        if not post_if_true.is_terminated():
            post_if_true.append(ir.Branch(tail))
        if not post_if_false.is_terminated():
            post_if_false.append(ir.Branch(tail))
        head.append(ir.BranchIf(cond, if_true, if_false))

        phi = self.append(ir.Phi(node.type))
        phi.add_incoming(true_result, post_if_true)
        phi.add_incoming(false_result, post_if_false)
        return phi

    def visit_NumT(self, node):
        return ir.Constant(node.n, node.type)

    def visit_StrT(self, node):
        return ir.Constant(node.s, node.type)

    def visit_NameConstantT(self, node):
        return ir.Constant(node.value, node.type)

    def _env_for(self, name):
        if name in self.current_globals:
            return self.append(ir.Builtin("globalenv", [self.current_env],
                                          self.current_env.type.outermost()))
        else:
            return self.current_env

    def _get_local(self, name):
        if self.current_class is not None and \
                name in self.current_class.type.attributes:
            return self.append(ir.GetAttr(self.current_class, name,
                                          name="FLD." + name))

        return self.append(ir.GetLocal(self._env_for(name), name,
                                       name="LOC." + name))

    def _set_local(self, name, value):
        if self.current_class is not None and \
                name in self.current_class.type.attributes:
            return self.append(ir.SetAttr(self.current_class, name, value))

        self.append(ir.SetLocal(self._env_for(name), name, value))

    def visit_NameT(self, node):
        if self.current_assign is None:
            insn = self._get_local(node.id)
            self.variable_map[node] = insn
            return insn
        else:
            return self._set_local(node.id, self.current_assign)

    def visit_AttributeT(self, node):
        try:
            old_assign, self.current_assign = self.current_assign, None
            obj = self.visit(node.value)
        finally:
            self.current_assign = old_assign

        if self.current_assign is None:
            return self.append(ir.GetAttr(obj, node.attr,
                                          name="{}.FLD.{}".format(_readable_name(obj), node.attr)))
        else:
            return self.append(ir.SetAttr(obj, node.attr, self.current_assign))

    def _make_check(self, cond, exn_gen, loc=None, params=[]):
        if loc is None:
            loc = self.current_loc

        try:
            name = "check:{}:{}".format(loc.line(), loc.column())
            args = [ir.EnvironmentArgument(self.current_env.type, "ARG.ENV")] + \
                   [ir.Argument(param.type, "ARG.{}".format(index))
                    for index, param in enumerate(params)]
            typ  = types.TFunction(OrderedDict([("arg{}".format(index), param.type)
                                                for index, param in enumerate(params)]),
                                   OrderedDict(),
                                   builtins.TNone())
            func = ir.Function(typ, ".".join(self.name + [name]), args, loc=loc)
            func.is_internal = True
            func.is_cold = True
            func.is_generated = True
            self.functions.append(func)
            old_func, self.current_function = self.current_function, func

            entry = self.add_block("entry")
            old_block, self.current_block = self.current_block, entry

            old_final_branch, self.final_branch = self.final_branch, None
            old_unwind, self.unwind_target = self.unwind_target, None
            self.raise_exn(exn_gen(*args[1:]), loc=loc)
        finally:
            self.current_function = old_func
            self.current_block = old_block
            self.final_branch = old_final_branch
            self.unwind_target = old_unwind

        # cond:    bool Value, condition
        # exn_gen: lambda()->exn Value, exception if condition not true
        cond_block = self.current_block

        self.current_block = body_block = self.add_block("check.body")
        closure = self.append(ir.Closure(func, ir.Constant(None, ir.TEnvironment("check", {}))))
        if self.unwind_target is None:
            insn = self.append(ir.Call(closure, params, {}))
        else:
            after_invoke = self.add_block("check.invoke")
            insn = self.append(ir.Invoke(closure, params, {}, after_invoke, self.unwind_target))
            self.current_block = after_invoke
        insn.is_cold = True
        self.append(ir.Unreachable())

        self.current_block = tail_block = self.add_block("check.tail")
        cond_block.append(ir.BranchIf(cond, tail_block, body_block))

    def _map_index(self, length, index, one_past_the_end=False, loc=None):
        lt_0          = self.append(ir.Compare(ast.Lt(loc=None),
                                               index, ir.Constant(0, index.type)))
        from_end      = self.append(ir.Arith(ast.Add(loc=None), length, index))
        mapped_index  = self.append(ir.Select(lt_0, from_end, index))
        mapped_ge_0   = self.append(ir.Compare(ast.GtE(loc=None),
                                               mapped_index, ir.Constant(0, mapped_index.type)))
        end_cmpop     = ast.LtE(loc=None) if one_past_the_end else ast.Lt(loc=None)
        mapped_lt_len = self.append(ir.Compare(end_cmpop, mapped_index, length))
        in_bounds     = self.append(ir.Select(mapped_ge_0, mapped_lt_len,
                                              ir.Constant(False, builtins.TBool())))
        head = self.current_block

        self._make_check(
            in_bounds,
            lambda index, length: self.alloc_exn(builtins.TException("IndexError"),
                ir.Constant("index {0} out of bounds 0:{1}", builtins.TStr()),
                index, length),
            params=[index, length],
            loc=loc)

        return mapped_index

    def _make_loop(self, init, cond_gen, body_gen, name="loop"):
        # init:     'iter Value, initial loop variable value
        # cond_gen: lambda('iter Value)->bool Value, loop condition
        # body_gen: lambda('iter Value)->'iter Value, loop body,
        #               returns next loop variable value
        init_block = self.current_block

        self.current_block = head_block = self.add_block("{}.head".format(name))
        init_block.append(ir.Branch(head_block))
        phi = self.append(ir.Phi(init.type))
        phi.add_incoming(init, init_block)
        cond = cond_gen(phi)

        self.current_block = body_block = self.add_block("{}.body".format(name))
        body = body_gen(phi)
        self.append(ir.Branch(head_block))
        phi.add_incoming(body, self.current_block)

        self.current_block = tail_block = self.add_block("{}.tail".format(name))
        head_block.append(ir.BranchIf(cond, body_block, tail_block))

        return head_block, body_block, tail_block

    def visit_SubscriptT(self, node):
        try:
            old_assign, self.current_assign = self.current_assign, None
            value = self.visit(node.value)
        finally:
            self.current_assign = old_assign

        if isinstance(node.slice, ast.Index):
            try:
                old_assign, self.current_assign = self.current_assign, None
                index = self.visit(node.slice.value)
            finally:
                self.current_assign = old_assign

            length = self.iterable_len(value, index.type)
            mapped_index = self._map_index(length, index,
                                           loc=node.begin_loc)
            if self.current_assign is None:
                result = self.iterable_get(value, mapped_index)
                result.set_name("{}.at.{}".format(value.name, _readable_name(index)))
                return result
            else:
                self.append(ir.SetElem(value, mapped_index, self.current_assign,
                                       name="{}.at.{}".format(value.name, _readable_name(index))))
        else: # Slice
            length = self.iterable_len(value, node.slice.type)

            if node.slice.lower is not None:
                try:
                    old_assign, self.current_assign = self.current_assign, None
                    start_index = self.visit(node.slice.lower)
                finally:
                    self.current_assign = old_assign
            else:
                start_index = ir.Constant(0, node.slice.type)
            mapped_start_index = self._map_index(length, start_index,
                                                 loc=node.begin_loc)

            if node.slice.upper is not None:
                try:
                    old_assign, self.current_assign = self.current_assign, None
                    stop_index = self.visit(node.slice.upper)
                finally:
                    self.current_assign = old_assign
            else:
                stop_index = length
            mapped_stop_index = self._map_index(length, stop_index, one_past_the_end=True,
                                                loc=node.begin_loc)

            if node.slice.step is not None:
                try:
                    old_assign, self.current_assign = self.current_assign, None
                    step = self.visit(node.slice.step)
                finally:
                    self.current_assign = old_assign

                self._make_check(
                    self.append(ir.Compare(ast.NotEq(loc=None), step, ir.Constant(0, step.type))),
                    lambda: self.alloc_exn(builtins.TException("ValueError"),
                        ir.Constant("step cannot be zero", builtins.TStr())),
                    loc=node.slice.step.loc)
            else:
                step = ir.Constant(1, node.slice.type)
            counting_up = self.append(ir.Compare(ast.Gt(loc=None), step,
                                                 ir.Constant(0, step.type)))

            unstepped_size = self.append(ir.Arith(ast.Sub(loc=None),
                                                  mapped_stop_index, mapped_start_index))
            slice_size_a = self.append(ir.Arith(ast.FloorDiv(loc=None), unstepped_size, step))
            slice_size_b = self.append(ir.Arith(ast.Mod(loc=None), unstepped_size, step))
            rem_not_empty = self.append(ir.Compare(ast.NotEq(loc=None), slice_size_b,
                                                   ir.Constant(0, slice_size_b.type)))
            slice_size_c = self.append(ir.Arith(ast.Add(loc=None), slice_size_a,
                                                ir.Constant(1, slice_size_a.type)))
            slice_size = self.append(ir.Select(rem_not_empty,
                                               slice_size_c, slice_size_a,
                                               name="slice.size"))
            self._make_check(
                self.append(ir.Compare(ast.LtE(loc=None), slice_size, length)),
                lambda slice_size, length: self.alloc_exn(builtins.TException("ValueError"),
                    ir.Constant("slice size {0} is larger than iterable length {1}",
                                builtins.TStr()),
                    slice_size, length),
                params=[slice_size, length],
                loc=node.slice.loc)

            if self.current_assign is None:
                is_neg_size = self.append(ir.Compare(ast.Lt(loc=None),
                                                     slice_size, ir.Constant(0, slice_size.type)))
                abs_slice_size = self.append(ir.Select(is_neg_size,
                                                       ir.Constant(0, slice_size.type), slice_size))
                other_value = self.append(ir.Alloc([abs_slice_size], value.type,
                                                   name="slice.result"))
            else:
                other_value = self.current_assign

            prehead = self.current_block

            head = self.current_block = self.add_block("slice.head")
            prehead.append(ir.Branch(head))

            index = self.append(ir.Phi(node.slice.type,
                                       name="slice.index"))
            index.add_incoming(mapped_start_index, prehead)
            other_index = self.append(ir.Phi(node.slice.type,
                                             name="slice.resindex"))
            other_index.add_incoming(ir.Constant(0, node.slice.type), prehead)

            # Still within bounds?
            bounded_up = self.append(ir.Compare(ast.Lt(loc=None), index, mapped_stop_index))
            bounded_down = self.append(ir.Compare(ast.Gt(loc=None), index, mapped_stop_index))
            within_bounds = self.append(ir.Select(counting_up, bounded_up, bounded_down))

            body = self.current_block = self.add_block("slice.body")

            if self.current_assign is None:
                elem = self.iterable_get(value, index)
                self.append(ir.SetElem(other_value, other_index, elem))
            else:
                elem = self.append(ir.GetElem(self.current_assign, other_index))
                self.append(ir.SetElem(value, index, elem))

            next_index = self.append(ir.Arith(ast.Add(loc=None), index, step))
            index.add_incoming(next_index, body)
            next_other_index = self.append(ir.Arith(ast.Add(loc=None), other_index,
                                                    ir.Constant(1, node.slice.type)))
            other_index.add_incoming(next_other_index, body)
            self.append(ir.Branch(head))

            tail = self.current_block = self.add_block("slice.tail")
            head.append(ir.BranchIf(within_bounds, body, tail))

            if self.current_assign is None:
                return other_value

    def visit_TupleT(self, node):
        if self.current_assign is None:
            return self.append(ir.Alloc([self.visit(elt) for elt in node.elts], node.type))
        else:
            try:
                old_assign = self.current_assign
                for index, elt_node in enumerate(node.elts):
                    self.current_assign = \
                        self.append(ir.GetAttr(old_assign, index,
                                               name="{}.e{}".format(old_assign.name, index)),
                                    loc=elt_node.loc)
                    self.visit(elt_node)
            finally:
                self.current_assign = old_assign

    def visit_ListT(self, node):
        if self.current_assign is None:
            elts = [self.visit(elt_node) for elt_node in node.elts]
            lst = self.append(ir.Alloc([ir.Constant(len(node.elts), self._size_type)],
                                       node.type))
            for index, elt_node in enumerate(elts):
                self.append(ir.SetElem(lst, ir.Constant(index, self._size_type), elt_node))
            return lst
        else:
            length = self.iterable_len(self.current_assign)
            self._make_check(
                self.append(ir.Compare(ast.Eq(loc=None), length,
                                       ir.Constant(len(node.elts), self._size_type))),
                lambda length: self.alloc_exn(builtins.TException("ValueError"),
                    ir.Constant("list must be {0} elements long to decompose", builtins.TStr()),
                    length),
                params=[length])

            for index, elt_node in enumerate(node.elts):
                elt = self.append(ir.GetElem(self.current_assign,
                                             ir.Constant(index, self._size_type)))
                try:
                    old_assign, self.current_assign = self.current_assign, elt
                    self.visit(elt_node)
                finally:
                    self.current_assign = old_assign

    def visit_ListCompT(self, node):
        assert len(node.generators) == 1
        comprehension = node.generators[0]
        assert comprehension.ifs == []

        iterable = self.visit(comprehension.iter)
        length = self.iterable_len(iterable)
        result = self.append(ir.Alloc([length], node.type))

        try:
            gen_suffix = ".gen@{}:{}".format(node.loc.line(), node.loc.column())
            env_type = ir.TEnvironment(name=self.current_function.name + gen_suffix,
                                       vars=node.typing_env, outer=self.current_env.type)
            env = self.append(ir.Alloc([], env_type, name="env.gen"))
            old_env, self.current_env = self.current_env, env

            self.append(ir.SetLocal(env, "$outer", old_env))

            def body_gen(index):
                elt = self.iterable_get(iterable, index)
                try:
                    old_assign, self.current_assign = self.current_assign, elt
                    self.visit(comprehension.target)
                finally:
                    self.current_assign = old_assign

                mapped_elt = self.visit(node.elt)
                self.append(ir.SetElem(result, index, mapped_elt))
                return self.append(ir.Arith(ast.Add(loc=None), index,
                                            ir.Constant(1, length.type)))
            self._make_loop(ir.Constant(0, length.type),
                lambda index: self.append(ir.Compare(ast.Lt(loc=None), index, length)),
                body_gen)

            return result
        finally:
            self.current_env = old_env

    def visit_BoolOpT(self, node):
        blocks = []
        for value_node in node.values:
            value_head = self.current_block
            value = self.visit(value_node)
            self.instrument_assert(value_node, value)
            value_tail = self.current_block

            blocks.append((value, value_head, value_tail))
            self.current_block = self.add_block("boolop.seq")

        tail = self.current_block
        phi = self.append(ir.Phi(node.type))
        for ((value, value_head, value_tail), (next_value_head, next_value_tail)) in \
                    zip(blocks, [(h,t) for (v,h,t) in blocks[1:]] + [(tail, tail)]):
            phi.add_incoming(value, value_tail)
            if next_value_head != tail:
                cond = self.coerce_to_bool(value, block=value_tail)
                if isinstance(node.op, ast.And):
                    value_tail.append(ir.BranchIf(cond, next_value_head, tail))
                else:
                    value_tail.append(ir.BranchIf(cond, tail, next_value_head))
            else:
                value_tail.append(ir.Branch(tail))
        return phi

    def visit_UnaryOpT(self, node):
        if isinstance(node.op, ast.Not):
            cond = self.coerce_to_bool(self.visit(node.operand))
            return self.append(ir.Select(cond,
                        ir.Constant(False, builtins.TBool()),
                        ir.Constant(True,  builtins.TBool())))
        elif isinstance(node.op, ast.Invert):
            operand = self.visit(node.operand)
            return self.append(ir.Arith(ast.BitXor(loc=None),
                                        ir.Constant(-1, operand.type), operand))
        elif isinstance(node.op, ast.USub):
            operand = self.visit(node.operand)
            return self.append(ir.Arith(ast.Sub(loc=None),
                                        ir.Constant(0, operand.type), operand))
        elif isinstance(node.op, ast.UAdd):
            # No-op.
            return self.visit(node.operand)
        else:
            assert False

    def visit_CoerceT(self, node):
        value = self.visit(node.value)
        if node.type.find() == value.type:
            return value
        else:
            return self.append(ir.Coerce(value, node.type,
                                         name="{}.{}".format(_readable_name(value),
                                                             node.type.name)))

    def visit_BinOpT(self, node):
        if builtins.is_numeric(node.type):
            lhs = self.visit(node.left)
            rhs = self.visit(node.right)
            if isinstance(node.op, (ast.LShift, ast.RShift)):
                # Check for negative shift amount.
                self._make_check(
                    self.append(ir.Compare(ast.GtE(loc=None), rhs, ir.Constant(0, rhs.type))),
                    lambda: self.alloc_exn(builtins.TException("ValueError"),
                        ir.Constant("shift amount must be nonnegative", builtins.TStr())),
                    loc=node.right.loc)
            elif isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)):
                self._make_check(
                    self.append(ir.Compare(ast.NotEq(loc=None), rhs, ir.Constant(0, rhs.type))),
                    lambda: self.alloc_exn(builtins.TException("ZeroDivisionError"),
                        ir.Constant("cannot divide by zero", builtins.TStr())),
                    loc=node.right.loc)

            return self.append(ir.Arith(node.op, lhs, rhs))
        elif isinstance(node.op, ast.Add): # list + list, tuple + tuple, str + str
            lhs, rhs = self.visit(node.left), self.visit(node.right)
            if types.is_tuple(node.left.type) and types.is_tuple(node.right.type):
                elts = []
                for index, elt in enumerate(node.left.type.elts):
                    elts.append(self.append(ir.GetAttr(lhs, index)))
                for index, elt in enumerate(node.right.type.elts):
                    elts.append(self.append(ir.GetAttr(rhs, index)))
                return self.append(ir.Alloc(elts, node.type))
            elif builtins.is_listish(node.left.type) and builtins.is_listish(node.right.type):
                lhs_length = self.iterable_len(lhs)
                rhs_length = self.iterable_len(rhs)

                result_length = self.append(ir.Arith(ast.Add(loc=None), lhs_length, rhs_length))
                result = self.append(ir.Alloc([result_length], node.type))

                # Copy lhs
                def body_gen(index):
                    elt = self.append(ir.GetElem(lhs, index))
                    self.append(ir.SetElem(result, index, elt))
                    return self.append(ir.Arith(ast.Add(loc=None), index,
                                                ir.Constant(1, self._size_type)))
                self._make_loop(ir.Constant(0, self._size_type),
                    lambda index: self.append(ir.Compare(ast.Lt(loc=None), index, lhs_length)),
                    body_gen)

                # Copy rhs
                def body_gen(index):
                    elt = self.append(ir.GetElem(rhs, index))
                    result_index = self.append(ir.Arith(ast.Add(loc=None), index, lhs_length))
                    self.append(ir.SetElem(result, result_index, elt))
                    return self.append(ir.Arith(ast.Add(loc=None), index,
                                                ir.Constant(1, self._size_type)))
                self._make_loop(ir.Constant(0, self._size_type),
                    lambda index: self.append(ir.Compare(ast.Lt(loc=None), index, rhs_length)),
                    body_gen)

                return result
            else:
                assert False
        elif isinstance(node.op, ast.Mult): # list * int, int * list
            lhs, rhs = self.visit(node.left), self.visit(node.right)
            if builtins.is_listish(lhs.type) and builtins.is_int(rhs.type):
                lst, num = lhs, rhs
            elif builtins.is_int(lhs.type) and builtins.is_listish(rhs.type):
                lst, num = rhs, lhs
            else:
                assert False

            lst_length = self.iterable_len(lst)

            result_length = self.append(ir.Arith(ast.Mult(loc=None), lst_length, num))
            result = self.append(ir.Alloc([result_length], node.type))

            # num times...
            def body_gen(num_index):
                # ... copy the list
                def body_gen(lst_index):
                    elt = self.append(ir.GetElem(lst, lst_index))
                    base_index = self.append(ir.Arith(ast.Mult(loc=None),
                                                      num_index, lst_length))
                    result_index = self.append(ir.Arith(ast.Add(loc=None),
                                                        base_index, lst_index))
                    self.append(ir.SetElem(result, base_index, elt))
                    return self.append(ir.Arith(ast.Add(loc=None), lst_index,
                                                ir.Constant(1, self._size_type)))
                self._make_loop(ir.Constant(0, self._size_type),
                    lambda index: self.append(ir.Compare(ast.Lt(loc=None), index, lst_length)),
                    body_gen)

                return self.append(ir.Arith(ast.Add(loc=None), num_index,
                                            ir.Constant(1, self._size_type)))
            self._make_loop(ir.Constant(0, self._size_type),
                lambda index: self.append(ir.Compare(ast.Lt(loc=None), index, num)),
                body_gen)

            return result
        else:
            assert False

    def polymorphic_compare_pair_order(self, op, lhs, rhs):
        if builtins.is_none(lhs.type) and builtins.is_none(rhs.type):
            return self.append(ir.Compare(op, lhs, rhs))
        elif builtins.is_numeric(lhs.type) and builtins.is_numeric(rhs.type):
            return self.append(ir.Compare(op, lhs, rhs))
        elif builtins.is_bool(lhs.type) and builtins.is_bool(rhs.type):
            return self.append(ir.Compare(op, lhs, rhs))
        elif types.is_tuple(lhs.type) and types.is_tuple(rhs.type):
            result = None
            for index in range(len(lhs.type.elts)):
                lhs_elt = self.append(ir.GetAttr(lhs, index))
                rhs_elt = self.append(ir.GetAttr(rhs, index))
                elt_result = self.polymorphic_compare_pair(op, lhs_elt, rhs_elt)
                if result is None:
                    result = elt_result
                else:
                    result = self.append(ir.Select(result, elt_result,
                                                   ir.Constant(False, builtins.TBool())))
            return result
        elif builtins.is_listish(lhs.type) and builtins.is_listish(rhs.type):
            head = self.current_block
            lhs_length = self.iterable_len(lhs)
            rhs_length = self.iterable_len(rhs)
            compare_length = self.append(ir.Compare(op, lhs_length, rhs_length))
            eq_length = self.append(ir.Compare(ast.Eq(loc=None), lhs_length, rhs_length))

            # If the length is the same, compare element-by-element
            # and break when the comparison result is false
            loop_head = self.add_block("compare.head")
            self.current_block = loop_head
            index_phi = self.append(ir.Phi(self._size_type))
            index_phi.add_incoming(ir.Constant(0, self._size_type), head)
            loop_cond = self.append(ir.Compare(ast.Lt(loc=None), index_phi, lhs_length))

            loop_body = self.add_block("compare.body")
            self.current_block = loop_body
            lhs_elt = self.append(ir.GetElem(lhs, index_phi))
            rhs_elt = self.append(ir.GetElem(rhs, index_phi))
            body_result = self.polymorphic_compare_pair(op, lhs_elt, rhs_elt)
            body_end = self.current_block

            loop_body2 = self.add_block("compare.body2")
            self.current_block = loop_body2
            index_next = self.append(ir.Arith(ast.Add(loc=None), index_phi,
                                              ir.Constant(1, self._size_type)))
            self.append(ir.Branch(loop_head))
            index_phi.add_incoming(index_next, loop_body2)

            tail = self.add_block("compare.tail")
            self.current_block = tail
            phi = self.append(ir.Phi(builtins.TBool()))
            head.append(ir.BranchIf(eq_length, loop_head, tail))
            phi.add_incoming(compare_length, head)
            loop_head.append(ir.BranchIf(loop_cond, loop_body, tail))
            phi.add_incoming(ir.Constant(True, builtins.TBool()), loop_head)
            body_end.append(ir.BranchIf(body_result, loop_body2, tail))
            phi.add_incoming(body_result, body_end)

            if isinstance(op, ast.NotEq):
                result = self.append(ir.Select(phi,
                    ir.Constant(False, builtins.TBool()), ir.Constant(True, builtins.TBool())))
            else:
                result = phi

            return result
        else:
            assert False

    def polymorphic_compare_pair_inclusion(self, needle, haystack):
        if builtins.is_range(haystack.type):
            # Optimized range `in` operator
            start       = self.append(ir.GetAttr(haystack, "start"))
            stop        = self.append(ir.GetAttr(haystack, "stop"))
            step        = self.append(ir.GetAttr(haystack, "step"))
            after_start = self.append(ir.Compare(ast.GtE(loc=None), needle, start))
            after_stop  = self.append(ir.Compare(ast.Lt(loc=None), needle, stop))
            from_start  = self.append(ir.Arith(ast.Sub(loc=None), needle, start))
            mod_step    = self.append(ir.Arith(ast.Mod(loc=None), from_start, step))
            on_step     = self.append(ir.Compare(ast.Eq(loc=None), mod_step,
                                                 ir.Constant(0, mod_step.type)))
            result      = self.append(ir.Select(after_start, after_stop,
                                                ir.Constant(False, builtins.TBool())))
            result      = self.append(ir.Select(result, on_step,
                                                ir.Constant(False, builtins.TBool())))
        elif builtins.is_iterable(haystack.type):
            length = self.iterable_len(haystack)

            cmp_result = loop_body2 = None
            def body_gen(index):
                nonlocal cmp_result, loop_body2

                elt = self.iterable_get(haystack, index)
                cmp_result = self.polymorphic_compare_pair(ast.Eq(loc=None), needle, elt)

                loop_body2 = self.add_block("compare.body")
                self.current_block = loop_body2
                return self.append(ir.Arith(ast.Add(loc=None), index,
                                            ir.Constant(1, length.type)))
            loop_head, loop_body, loop_tail = \
                self._make_loop(ir.Constant(0, length.type),
                    lambda index: self.append(ir.Compare(ast.Lt(loc=None), index, length)),
                    body_gen, name="compare")

            loop_body.append(ir.BranchIf(cmp_result, loop_tail, loop_body2))
            phi = loop_tail.prepend(ir.Phi(builtins.TBool()))
            phi.add_incoming(ir.Constant(False, builtins.TBool()), loop_head)
            phi.add_incoming(ir.Constant(True, builtins.TBool()), loop_body)

            result = phi
        else:
            assert False

        return result

    def invert(self, value):
        return self.append(ir.Select(value,
                    ir.Constant(False, builtins.TBool()),
                    ir.Constant(True, builtins.TBool())))

    def polymorphic_compare_pair(self, op, lhs, rhs):
        if isinstance(op, (ast.Is, ast.IsNot)):
            # The backend will handle equality of aggregates.
            return self.append(ir.Compare(op, lhs, rhs))
        elif isinstance(op, ast.In):
            return self.polymorphic_compare_pair_inclusion(lhs, rhs)
        elif isinstance(op, ast.NotIn):
            result = self.polymorphic_compare_pair_inclusion(lhs, rhs)
            return self.invert(result)
        elif isinstance(op, (ast.Eq, ast.Lt, ast.LtE, ast.Gt, ast.GtE)):
            return self.polymorphic_compare_pair_order(op, lhs, rhs)
        elif isinstance(op, ast.NotEq):
            result = self.polymorphic_compare_pair_order(ast.Eq(loc=op.loc), lhs, rhs)
            return self.invert(result)
        else:
            assert False

    def visit_CompareT(self, node):
        # Essentially a sequence of `and`s performed over results
        # of comparisons.
        blocks = []
        lhs = self.visit(node.left)
        self.instrument_assert(node.left, lhs)
        for op, rhs_node in zip(node.ops, node.comparators):
            result_head = self.current_block
            rhs = self.visit(rhs_node)
            self.instrument_assert(rhs_node, rhs)
            result = self.polymorphic_compare_pair(op, lhs, rhs)
            result_tail = self.current_block

            blocks.append((result, result_head, result_tail))
            self.current_block = self.add_block("compare.seq")
            lhs = rhs

        tail = self.current_block
        phi = self.append(ir.Phi(node.type))
        for ((result, result_head, result_tail), (next_result_head, next_result_tail)) in \
                    zip(blocks, [(h,t) for (v,h,t) in blocks[1:]] + [(tail, tail)]):
            phi.add_incoming(result, result_tail)
            if next_result_head != tail:
                result_tail.append(ir.BranchIf(result, next_result_head, tail))
            else:
                result_tail.append(ir.Branch(tail))
        return phi

    # Keep this function with builtins.TException.attributes.
    def alloc_exn(self, typ, message=None, param0=None, param1=None, param2=None):
        typ = typ.find()
        name = "{}:{}".format(typ.id, typ.name)
        attributes = [
            ir.Constant(name,           builtins.TStr()),   # typeinfo
            ir.Constant("<not thrown>", builtins.TStr()),   # file
            ir.Constant(0,              builtins.TInt32()), # line
            ir.Constant(0,              builtins.TInt32()), # column
            ir.Constant("<not thrown>", builtins.TStr()),   # function
        ]

        if message is None:
            attributes.append(ir.Constant(typ.name, builtins.TStr()))
        else:
            attributes.append(message)                    # message

        param_type = builtins.TInt64()
        for param in [param0, param1, param2]:
            if param is None:
                attributes.append(ir.Constant(0, builtins.TInt64()))
            else:
                if param.type != param_type:
                    param = self.append(ir.Coerce(param, param_type))
                attributes.append(param)                  # paramN, N=0:2

        return self.append(ir.Alloc(attributes, typ))

    def visit_builtin_call(self, node):
        # A builtin by any other name... Ignore node.func, just use the type.
        typ = node.func.type
        if types.is_builtin(typ, "bool"):
            if len(node.args) == 0 and len(node.keywords) == 0:
                return ir.Constant(False, builtins.TBool())
            elif len(node.args) == 1 and len(node.keywords) == 0:
                arg = self.visit(node.args[0])
                return self.coerce_to_bool(arg)
            else:
                assert False
        elif types.is_builtin(typ, "int") or \
                types.is_builtin(typ, "int32") or types.is_builtin(typ, "int64"):
            if len(node.args) == 0 and len(node.keywords) == 0:
                return ir.Constant(0, node.type)
            elif len(node.args) == 1 and \
                    (len(node.keywords) == 0 or \
                     len(node.keywords) == 1 and node.keywords[0].arg == 'width'):
                # The width argument is purely type-level
                arg = self.visit(node.args[0])
                return self.append(ir.Coerce(arg, node.type))
            else:
                assert False
        elif types.is_builtin(typ, "float"):
            if len(node.args) == 0 and len(node.keywords) == 0:
                return ir.Constant(0.0, builtins.TFloat())
            elif len(node.args) == 1 and len(node.keywords) == 0:
                arg = self.visit(node.args[0])
                return self.append(ir.Coerce(arg, node.type))
            else:
                assert False
        elif (types.is_builtin(typ, "list") or types.is_builtin(typ, "array") or
              types.is_builtin(typ, "bytearray") or types.is_builtin(typ, "bytes")):
            if len(node.args) == 0 and len(node.keywords) == 0:
                length = ir.Constant(0, builtins.TInt32())
                return self.append(ir.Alloc([length], node.type))
            elif len(node.args) == 1 and len(node.keywords) == 0:
                arg = self.visit(node.args[0])
                length = self.iterable_len(arg)
                result = self.append(ir.Alloc([length], node.type))

                def body_gen(index):
                    elt = self.iterable_get(arg, index)
                    elt = self.append(ir.Coerce(elt, builtins.get_iterable_elt(node.type)))
                    self.append(ir.SetElem(result, index, elt))
                    return self.append(ir.Arith(ast.Add(loc=None), index,
                                                ir.Constant(1, length.type)))
                self._make_loop(ir.Constant(0, length.type),
                    lambda index: self.append(ir.Compare(ast.Lt(loc=None), index, length)),
                    body_gen)

                return result
            else:
                assert False
        elif types.is_builtin(typ, "range"):
            elt_typ = builtins.get_iterable_elt(node.type)
            if len(node.args) == 1 and len(node.keywords) == 0:
                max_arg = self.visit(node.args[0])
                return self.append(ir.Alloc([
                    ir.Constant(elt_typ.zero(), elt_typ),
                    max_arg,
                    ir.Constant(elt_typ.one(), elt_typ),
                ], node.type))
            elif len(node.args) == 2 and len(node.keywords) == 0:
                min_arg = self.visit(node.args[0])
                max_arg = self.visit(node.args[1])
                return self.append(ir.Alloc([
                    min_arg,
                    max_arg,
                    ir.Constant(elt_typ.one(), elt_typ),
                ], node.type))
            elif len(node.args) == 3 and len(node.keywords) == 0:
                min_arg = self.visit(node.args[0])
                max_arg = self.visit(node.args[1])
                step_arg = self.visit(node.args[2])
                return self.append(ir.Alloc([
                    min_arg,
                    max_arg,
                    step_arg,
                ], node.type))
            else:
                assert False
        elif types.is_builtin(typ, "len"):
            if len(node.args) == 1 and len(node.keywords) == 0:
                arg = self.visit(node.args[0])
                return self.iterable_len(arg)
            else:
                assert False
        elif types.is_builtin(typ, "round"):
            if len(node.args) == 1 and len(node.keywords) == 0:
                arg = self.visit(node.args[0])
                return self.append(ir.Builtin("round", [arg], node.type))
            else:
                assert False
        elif types.is_builtin(typ, "abs"):
            if len(node.args) == 1 and len(node.keywords) == 0:
                arg = self.visit(node.args[0])
                neg = self.append(
                    ir.Arith(ast.Sub(loc=None), ir.Constant(0, arg.type), arg))
                cond = self.append(
                    ir.Compare(ast.Lt(loc=None), arg, ir.Constant(0, arg.type)))
                return self.append(ir.Select(cond, neg, arg))
            else:
                assert False
        elif types.is_builtin(typ, "min"):
            if len(node.args) == 2 and len(node.keywords) == 0:
                arg0, arg1 = map(self.visit, node.args)
                cond = self.append(ir.Compare(ast.Lt(loc=None), arg0, arg1))
                return self.append(ir.Select(cond, arg0, arg1))
            else:
                assert False
        elif types.is_builtin(typ, "max"):
            if len(node.args) == 2 and len(node.keywords) == 0:
                arg0, arg1 = map(self.visit, node.args)
                cond = self.append(ir.Compare(ast.Gt(loc=None), arg0, arg1))
                return self.append(ir.Select(cond, arg0, arg1))
            else:
                assert False
        elif types.is_builtin(typ, "make_array"):
            if len(node.args) == 2 and len(node.keywords) == 0:
                arg0, arg1 = map(self.visit, node.args)

                result = self.append(ir.Alloc([arg0], node.type))
                def body_gen(index):
                    self.append(ir.SetElem(result, index, arg1))
                    return self.append(ir.Arith(ast.Add(loc=None), index,
                                                ir.Constant(1, arg0.type)))
                self._make_loop(ir.Constant(0, self._size_type),
                                lambda index: self.append(ir.Compare(ast.Lt(loc=None), index, arg0)),
                                body_gen)
                return result
            else:
                assert False
        elif types.is_builtin(typ, "print"):
            self.polymorphic_print([self.visit(arg) for arg in node.args],
                                   separator=" ", suffix="\n")
            return ir.Constant(None, builtins.TNone())
        elif types.is_builtin(typ, "rtio_log"):
            prefix, *args = node.args
            self.polymorphic_print([self.visit(prefix)],
                                   separator=" ", suffix="\x1E", as_rtio=True)
            self.polymorphic_print([self.visit(arg) for arg in args],
                                   separator=" ", suffix="\x1D", as_rtio=True)
            return ir.Constant(None, builtins.TNone())
        elif types.is_builtin(typ, "delay"):
            if len(node.args) == 1 and len(node.keywords) == 0:
                arg = self.visit(node.args[0])
                arg_mu_float = self.append(ir.Arith(ast.Div(loc=None), arg, self.ref_period))
                arg_mu = self.append(ir.Builtin("round", [arg_mu_float], builtins.TInt64()))
                return self.append(ir.Builtin("delay_mu", [arg_mu], builtins.TNone()))
            else:
                assert False
        elif types.is_builtin(typ, "now_mu") or types.is_builtin(typ, "delay_mu") \
                or types.is_builtin(typ, "at_mu"):
            return self.append(ir.Builtin(typ.name,
                                          [self.visit(arg) for arg in node.args], node.type))
        elif types.is_exn_constructor(typ):
            return self.alloc_exn(node.type, *[self.visit(arg_node) for arg_node in node.args])
        elif types.is_constructor(typ):
            return self.append(ir.Alloc([], typ.instance))
        else:
            diag = diagnostic.Diagnostic("error",
                "builtin function '{name}' cannot be used in this context",
                {"name": typ.find().name},
                node.loc)
            self.engine.process(diag)

    def _user_call(self, callee, positional, keywords, arg_exprs={}):
        if types.is_function(callee.type) or types.is_rpc(callee.type):
            func     = callee
            self_arg = None
            fn_typ   = callee.type
            offset   = 0
        elif types.is_method(callee.type):
            func     = self.append(ir.GetAttr(callee, "__func__",
                                              name="{}.ENV".format(callee.name)))
            self_arg = self.append(ir.GetAttr(callee, "__self__",
                                              name="{}.SLF".format(callee.name)))
            fn_typ   = types.get_method_function(callee.type)
            offset   = 1
        else:
            assert False

        if types.is_rpc(fn_typ):
            if self_arg is None:
                args = positional
            else:
                args = [self_arg] + positional

            for keyword in keywords:
                arg = keywords[keyword]
                args.append(self.append(ir.Alloc([ir.Constant(keyword, builtins.TStr()), arg],
                                                 ir.TKeyword(arg.type))))
        else:
            args = [None] * (len(fn_typ.args) + len(fn_typ.optargs))

            for index, arg in enumerate(positional):
                if index + offset < len(fn_typ.args):
                    args[index + offset] = arg
                else:
                    args[index + offset] = self.append(ir.Alloc([arg], ir.TOption(arg.type)))

            for keyword in keywords:
                arg = keywords[keyword]
                if keyword in fn_typ.args:
                    for index, arg_name in enumerate(fn_typ.args):
                        if keyword == arg_name:
                            assert args[index] is None
                            args[index] = arg
                            break
                elif keyword in fn_typ.optargs:
                    for index, optarg_name in enumerate(fn_typ.optargs):
                        if keyword == optarg_name:
                            assert args[len(fn_typ.args) + index] is None
                            args[len(fn_typ.args) + index] = \
                                    self.append(ir.Alloc([arg], ir.TOption(arg.type)))
                            break

            for index, optarg_name in enumerate(fn_typ.optargs):
                if args[len(fn_typ.args) + index] is None:
                    args[len(fn_typ.args) + index] = \
                            self.append(ir.Alloc([], ir.TOption(fn_typ.optargs[optarg_name])))

            if self_arg is not None:
                assert args[0] is None
                args[0] = self_arg

            assert None not in args

        if self.unwind_target is None or \
                types.is_c_function(callee.type) and "nounwind" in callee.type.flags:
            insn = self.append(ir.Call(func, args, arg_exprs))
        else:
            after_invoke = self.add_block("invoke")
            insn = self.append(ir.Invoke(func, args, arg_exprs,
                                         after_invoke, self.unwind_target))
            self.current_block = after_invoke

        return insn

    def visit_CallT(self, node):
        if not types.is_builtin(node.func.type):
            callee   = self.visit(node.func)
            args     = [self.visit(arg_node) for arg_node in node.args]
            keywords = {kw_node.arg: self.visit(kw_node.value) for kw_node in node.keywords}

        if node.iodelay is not None and not iodelay.is_const(node.iodelay, 0):
            before_delay = self.current_block
            during_delay = self.add_block("delay.head")
            before_delay.append(ir.Branch(during_delay))
            self.current_block = during_delay

        if types.is_builtin(node.func.type):
            insn = self.visit_builtin_call(node)
        else:
            insn = self._user_call(callee, args, keywords, node.arg_exprs)

            if isinstance(node.func, asttyped.AttributeT):
                attr_node = node.func
                self.method_map[(attr_node.value.type.find(), attr_node.attr)].append(insn)

        if node.iodelay is not None and not iodelay.is_const(node.iodelay, 0):
            after_delay = self.add_block("delay.tail")
            self.append(ir.Delay(node.iodelay, insn, after_delay))
            self.current_block = after_delay

        return insn

    def visit_QuoteT(self, node):
        return self.append(ir.Quote(node.value, node.type))

    def instrument_assert(self, node, value):
        if self.current_assert_env is not None:
            if isinstance(value, ir.Constant):
                return # don't display the values of constants

            if any([algorithm.compare(node, subexpr)
                    for (subexpr, name) in self.current_assert_subexprs]):
                return # don't display the same subexpression twice

            name = self.current_assert_env.type.add("$subexpr", ir.TOption(node.type))
            value_opt = self.append(ir.Alloc([value], ir.TOption(node.type)),
                                    loc=node.loc)
            self.append(ir.SetLocal(self.current_assert_env, name, value_opt),
                        loc=node.loc)
            self.current_assert_subexprs.append((node, name))

    def visit_Assert(self, node):
        try:
            assert_suffix   = ".assert@{}:{}".format(node.loc.line(), node.loc.column())
            assert_env_type = ir.TEnvironment(name=self.current_function.name + assert_suffix,
                                              vars={})
            assert_env = self.current_assert_env = \
                self.append(ir.Alloc([], assert_env_type, name="assertenv"))
            assert_subexprs = self.current_assert_subexprs = []
            init = self.current_block

            prehead = self.current_block = self.add_block("assert.prehead")
            cond = self.visit(node.test)
            head = self.current_block
        finally:
            self.current_assert_env = None
            self.current_assert_subexprs = None

        for subexpr_node, subexpr_name in assert_subexprs:
            empty = init.append(ir.Alloc([], ir.TOption(subexpr_node.type)))
            init.append(ir.SetLocal(assert_env, subexpr_name, empty))
        init.append(ir.Branch(prehead))

        if_failed = self.current_block = self.add_block("assert.fail")

        if node.msg:
            explanation = node.msg.s
        else:
            explanation = node.loc.source()
        self.append(ir.Builtin("printf", [
                ir.Constant("assertion failed at %.*s: %.*s\n\x00", builtins.TStr()),
                ir.Constant(str(node.loc.begin()), builtins.TStr()),
                ir.Constant(str(explanation), builtins.TStr()),
            ], builtins.TNone()))

        for subexpr_node, subexpr_name in assert_subexprs:
            subexpr_head = self.current_block
            subexpr_value_opt = self.append(ir.GetLocal(assert_env, subexpr_name))
            subexpr_cond = self.append(ir.Builtin("is_some", [subexpr_value_opt],
                                                  builtins.TBool()))

            subexpr_body = self.current_block = self.add_block("assert.subexpr.body")
            self.append(ir.Builtin("printf", [
                    ir.Constant("  (%.*s) = \x00", builtins.TStr()),
                    ir.Constant(subexpr_node.loc.source(), builtins.TStr())
                ], builtins.TNone()))
            subexpr_value = self.append(ir.Builtin("unwrap", [subexpr_value_opt],
                                                   subexpr_node.type))
            self.polymorphic_print([subexpr_value], separator="", suffix="\n")
            subexpr_postbody = self.current_block

            subexpr_tail = self.current_block = self.add_block("assert.subexpr.tail")
            self.append(ir.Branch(subexpr_tail), block=subexpr_postbody)
            self.append(ir.BranchIf(subexpr_cond, subexpr_body, subexpr_tail), block=subexpr_head)

        self.append(ir.Builtin("abort", [], builtins.TNone()))
        self.append(ir.Unreachable())

        tail = self.current_block = self.add_block("assert.tail")
        self.append(ir.BranchIf(cond, tail, if_failed), block=head)

    def polymorphic_print(self, values, separator, suffix="", as_repr=False, as_rtio=False):
        def printf(format_string, *args):
            format = ir.Constant(format_string, builtins.TStr())
            if as_rtio:
                self.append(ir.Builtin("rtio_log", [format, *args], builtins.TNone()))
            else:
                self.append(ir.Builtin("printf", [format, *args], builtins.TNone()))

        format_string = ""
        args = []
        def flush():
            nonlocal format_string, args
            if format_string != "":
                printf(format_string + "\x00", *args)
                format_string = ""
                args = []

        for value in values:
            if format_string != "":
                format_string += separator

            if types.is_tuple(value.type):
                format_string += "("; flush()
                self.polymorphic_print([self.append(ir.GetAttr(value, index))
                                        for index in range(len(value.type.elts))],
                                       separator=", ", as_repr=True, as_rtio=as_rtio)
                if len(value.type.elts) == 1:
                    format_string += ",)"
                else:
                    format_string += ")"
            elif types.is_function(value.type):
                format_string += "<closure %p(%p)>"
                args.append(self.append(ir.GetAttr(value, '__code__')))
                args.append(self.append(ir.GetAttr(value, '__closure__')))
            elif builtins.is_none(value.type):
                format_string += "None"
            elif builtins.is_bool(value.type):
                format_string += "%.*s"
                args.append(self.append(ir.Select(value,
                                                  ir.Constant("True", builtins.TStr()),
                                                  ir.Constant("False", builtins.TStr()))))
            elif builtins.is_int(value.type):
                width = builtins.get_int_width(value.type)
                if width <= 32:
                    format_string += "%d"
                elif width <= 64:
                    format_string += "%lld"
                else:
                    assert False
                args.append(value)
            elif builtins.is_float(value.type):
                format_string += "%g"
                args.append(value)
            elif builtins.is_str(value.type):
                if as_repr:
                    format_string += "\"%.*s\""
                else:
                    format_string += "%.*s"
                args.append(value)
            elif builtins.is_listish(value.type):
                if builtins.is_list(value.type):
                    format_string += "["; flush()
                elif builtins.is_bytes(value.type):
                    format_string += "bytes(["; flush()
                elif builtins.is_bytearray(value.type):
                    format_string += "bytearray(["; flush()
                elif builtins.is_array(value.type):
                    format_string += "array(["; flush()
                else:
                    assert False

                length = self.iterable_len(value)
                last = self.append(ir.Arith(ast.Sub(loc=None), length, ir.Constant(1, length.type)))
                def body_gen(index):
                    elt = self.iterable_get(value, index)
                    self.polymorphic_print([elt], separator="", as_repr=True, as_rtio=as_rtio)
                    is_last = self.append(ir.Compare(ast.Lt(loc=None), index, last))
                    head = self.current_block

                    if_last = self.current_block = self.add_block("print.comma")
                    printf(", \x00")

                    tail = self.current_block = self.add_block("print.tail")
                    if_last.append(ir.Branch(tail))
                    head.append(ir.BranchIf(is_last, if_last, tail))

                    return self.append(ir.Arith(ast.Add(loc=None), index,
                                                ir.Constant(1, length.type)))
                self._make_loop(ir.Constant(0, length.type),
                    lambda index: self.append(ir.Compare(ast.Lt(loc=None), index, length)),
                    body_gen)

                if builtins.is_list(value.type):
                    format_string += "]"
                elif (builtins.is_bytes(value.type) or builtins.is_bytearray(value.type) or
                      builtins.is_array(value.type)):
                    format_string += "])"
            elif builtins.is_range(value.type):
                format_string += "range("; flush()

                start  = self.append(ir.GetAttr(value, "start"))
                stop   = self.append(ir.GetAttr(value, "stop"))
                step   = self.append(ir.GetAttr(value, "step"))
                self.polymorphic_print([start, stop, step], separator=", ", as_rtio=as_rtio)

                format_string += ")"
            elif builtins.is_exception(value.type):
                name    = self.append(ir.GetAttr(value, "__name__"))
                message = self.append(ir.GetAttr(value, "__message__"))
                param1  = self.append(ir.GetAttr(value, "__param0__"))
                param2  = self.append(ir.GetAttr(value, "__param1__"))
                param3  = self.append(ir.GetAttr(value, "__param2__"))

                format_string += "%.*s(%.*s, %lld, %lld, %lld)"
                args += [name, message, param1, param2, param3]
            else:
                assert False

        format_string += suffix
        flush()
