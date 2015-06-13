from pythonparser import source, ast, algorithm, diagnostic, parse_buffer
from . import asttyped, types, builtins

# This visitor will be called for every node with a scope,
# i.e.: class, function, comprehension, lambda
class LocalExtractor(algorithm.Visitor):
    def __init__(self, env_stack, engine):
        super().__init__()
        self.env_stack  = env_stack
        self.engine     = engine

        self.in_root    = False
        self.in_assign  = False
        self.typing_env = {}

        # which names are global have to be recorded in the current scope
        self.global_    = set()

        # which names are nonlocal only affects whether the current scope
        # gets a new binding or not, so we throw this away
        self.nonlocal_  = set()

        # parameters can't be declared as global or nonlocal
        self.params     = set()

    def visit_in_assign(self, node):
        try:
            self.in_assign = True
            return self.visit(node)
        finally:
            self.in_assign = False

    def visit_Assign(self, node):
        for target in node.targets:
            self.visit_in_assign(target)
        self.visit(node.value)

    def visit_For(self, node):
        self.visit_in_assign(node.target)
        self.visit(node.iter)
        self.visit(node.body)
        self.visit(node.orelse)

    def visit_withitem(self, node):
        self.visit(node.context_expr)
        if node.optional_vars is not None:
            self.visit_in_assign(node.optional_vars)

    def visit_comprehension(self, node):
        self.visit_in_assign(node.target)
        self.visit(node.iter)
        for if_ in node.ifs:
            self.visit(node.ifs)

    def visit_root(self, node):
        if self.in_root:
            return
        self.in_root = True
        self.generic_visit(node)

    visit_ClassDef     = visit_root # don't look at inner scopes
    visit_FunctionDef  = visit_root
    visit_Lambda       = visit_root
    visit_DictComp     = visit_root
    visit_ListComp     = visit_root
    visit_SetComp      = visit_root
    visit_GeneratorExp = visit_root

    def _assignable(self, name):
        if name not in self.typing_env and name not in self.nonlocal_:
            self.typing_env[name] = types.TVar()

    def visit_arg(self, node):
        self._assignable(node.arg)
        self.params.add(node.arg)

    def visit_Name(self, node):
        if self.in_assign:
            # code like:
            # x = 1
            # def f():
            #   x = 1
            # creates a new binding for x in f's scope
            self._assignable(node.id)

    def _check_not_in(self, name, names, curkind, newkind, loc):
        if name in names:
            diag = diagnostic.Diagnostic("error",
                "name '{name}' cannot be {curkind} and {newkind} simultaneously",
                {"name": name, "curkind": curkind, "newkind": newkind}, loc)
            self.engine.process(diag)
            return True
        return False

    def visit_Global(self, node):
        for name, loc in zip(node.names, node.name_locs):
            if self._check_not_in(name, self.nonlocal_, "nonlocal", "global", loc) or \
                    self._check_not_in(name, self.params, "a parameter", "global", loc):
               continue
            self.global_.add(name)

    def visit_Nonlocal(self, node):
        for name, loc in zip(node.names, node.name_locs):
            if self._check_not_in(name, self.global_, "global", "nonlocal", loc) or \
                    self._check_not_in(name, self.params, "a parameter", "nonlocal", loc):
                continue

            found = False
            for outer_env in reversed(self.env_stack):
                if name in outer_env:
                    found = True
                    break
            if not found:
                diag = diagnostic.Diagnostic("error",
                    "cannot declare name '{name}' as nonlocal: it is not bound in any outer scope",
                    {"name": name},
                    loc, [node.keyword_loc])
                self.engine.process(diag)
                continue

            self.nonlocal_.add(name)

    def visit_ExceptHandler(self, node):
        self.visit(node.type)
        self._assignable(node.name)
        for stmt in node.body:
            self.visit(stmt)


class ASTTypedRewriter(algorithm.Transformer):
    """
    :class:`ASTTypedRewriter` converts an untyped AST to a typed AST
    where all type fields of non-literals are filled with fresh type variables,
    and type fields of literals are filled with corresponding types.

    :class:`ASTTypedRewriter` also discovers the scope of variable bindings
    via :class:`LocalExtractor`.
    """

    def __init__(self, engine):
        self.engine = engine
        self.env_stack = []

    def _find_name(self, name, loc):
        for typing_env in reversed(self.env_stack):
            if name in typing_env:
                return typing_env[name]
        diag = diagnostic.Diagnostic("fatal",
            "name '{name}' is not bound to anything", {"name":name}, loc)
        self.engine.process(diag)

    # Visitors that replace node with a typed node
    #
    def visit_Module(self, node):
        extractor = LocalExtractor(env_stack=self.env_stack, engine=self.engine)
        extractor.visit(node)

        node = asttyped.ModuleT(
            typing_env=extractor.typing_env, globals_in_scope=extractor.global_,
            body=node.body, loc=node.loc)

        try:
            self.env_stack.append(node.typing_env)
            return self.generic_visit(node)
        finally:
            self.env_stack.pop()

    def visit_FunctionDef(self, node):
        extractor = LocalExtractor(env_stack=self.env_stack, engine=self.engine)
        extractor.visit(node)

        node = asttyped.FunctionDefT(
            typing_env=extractor.typing_env, globals_in_scope=extractor.global_,
            return_type=types.TVar(),
            name=node.name, args=node.args, returns=node.returns,
            body=node.body, decorator_list=node.decorator_list,
            keyword_loc=node.keyword_loc, name_loc=node.name_loc,
            arrow_loc=node.arrow_loc, colon_loc=node.colon_loc, at_locs=node.at_locs,
            loc=node.loc)

        try:
            self.env_stack.append(node.typing_env)
            return self.generic_visit(node)
        finally:
            self.env_stack.pop()

    def visit_arg(self, node):
        return asttyped.argT(type=self._find_name(node.arg, node.loc),
                             arg=node.arg, annotation=self.visit(node.annotation),
                             arg_loc=node.arg_loc, colon_loc=node.colon_loc, loc=node.loc)

    def visit_Num(self, node):
        if isinstance(node.n, int):
            typ = builtins.TInt()
        elif isinstance(node.n, float):
            typ = builtins.TFloat()
        else:
            diag = diagnostic.Diagnostic("fatal",
                "numeric type {type} is not supported", {"type": node.n.__class__.__name__},
                node.loc)
            self.engine.process(diag)
        return asttyped.NumT(type=typ,
                             n=node.n, loc=node.loc)

    def visit_Name(self, node):
        return asttyped.NameT(type=self._find_name(node.id, node.loc),
                              id=node.id, ctx=node.ctx, loc=node.loc)

    def visit_NameConstant(self, node):
        if node.value is True or node.value is False:
            typ = builtins.TBool()
        elif node.value is None:
            typ = builtins.TNone()
        return asttyped.NameConstantT(type=typ, value=node.value, loc=node.loc)

    def visit_Tuple(self, node):
        node = self.generic_visit(node)
        return asttyped.TupleT(type=builtins.TTuple([x.type for x in node.elts]),
                               elts=node.elts, ctx=node.ctx, loc=node.loc)

    def visit_List(self, node):
        node = self.generic_visit(node)
        node = asttyped.ListT(type=builtins.TList(),
                              elts=node.elts, ctx=node.ctx, loc=node.loc)
        return self.visit(node)

    def visit_Subscript(self, node):
        node = self.generic_visit(node)
        node = asttyped.SubscriptT(type=types.TVar(),
                                   value=node.value, slice=node.slice, ctx=node.ctx,
                                   loc=node.loc)
        return self.visit(node)

    def visit_IfExp(self, node):
        node = self.generic_visit(node)
        node = asttyped.IfExpT(type=types.TVar(),
                               test=node.test, body=node.body, orelse=node.orelse,
                               if_loc=node.if_loc, else_loc=node.else_loc, loc=node.loc)
        return self.visit(node)

    def visit_BoolOp(self, node):
        node = self.generic_visit(node)
        node = asttyped.BoolOpT(type=types.TVar(),
                                op=node.op, values=node.values,
                                op_locs=node.op_locs, loc=node.loc)
        return self.visit(node)

    def visit_UnaryOp(self, node):
        node = self.generic_visit(node)
        node = asttyped.UnaryOpT(type=types.TVar(),
                                 op=node.op, operand=node.operand,
                                 loc=node.loc)
        return self.visit(node)

    def visit_BinOp(self, node):
        node = self.generic_visit(node)
        node = asttyped.BinOpT(type=types.TVar(),
                               left=node.left, op=node.op, right=node.right,
                               loc=node.loc)
        return self.visit(node)

    def visit_Compare(self, node):
        node = self.generic_visit(node)
        node = asttyped.CompareT(type=types.TVar(),
                                 left=node.left, ops=node.ops, comparators=node.comparators,
                                 loc=node.loc)
        return self.visit(node)

    # Unsupported visitors
    #
    def visit_unsupported(self, node):
        diag = diagnostic.Diagnostic("fatal",
            "this syntax is not supported", {},
            node.loc)
        self.engine.process(diag)

    # expr
    visit_Attribute = visit_unsupported
    visit_BinOp = visit_unsupported
    visit_Call = visit_unsupported
    visit_Compare = visit_unsupported
    visit_Dict = visit_unsupported
    visit_DictComp = visit_unsupported
    visit_Ellipsis = visit_unsupported
    visit_GeneratorExp = visit_unsupported
    visit_Lambda = visit_unsupported
    visit_ListComp = visit_unsupported
    visit_Set = visit_unsupported
    visit_SetComp = visit_unsupported
    visit_Str = visit_unsupported
    visit_Starred = visit_unsupported
    visit_Yield = visit_unsupported
    visit_YieldFrom = visit_unsupported

    # stmt
    visit_Assert = visit_unsupported
    visit_ClassDef = visit_unsupported
    visit_Delete = visit_unsupported
    visit_Import = visit_unsupported
    visit_ImportFrom = visit_unsupported
    visit_Raise = visit_unsupported
    visit_Try = visit_unsupported
    visit_With = visit_unsupported


class Inferencer(algorithm.Visitor):
    """
    :class:`Inferencer` infers types by recursively applying the unification
    algorithm. It does not treat inability to infer a concrete type as an error;
    the result can still contain type variables.

    :class:`Inferencer` is idempotent, but does not guarantee that it will
    perform all possible inference in a single pass.
    """

    def __init__(self, engine):
        self.engine = engine
        self.function = None # currently visited function, for Return inference
        self.in_loop = False

    def _unify(self, typea, typeb, loca, locb, makenotes=None):
        try:
            typea.unify(typeb)
        except types.UnificationError as e:
            printer = types.TypePrinter()

            if makenotes:
                notes = makenotes(printer, typea, typeb, loca, locb)
            else:
                notes = [
                    diagnostic.Diagnostic("note",
                        "expression of type {typea}",
                        {"typea": printer.name(typea)},
                        loca),
                    diagnostic.Diagnostic("note",
                        "expression of type {typeb}",
                        {"typeb": printer.name(typeb)},
                        locb)
                ]

            highlights = [locb] if locb else []
            if e.typea.find() == typea.find() and e.typeb.find() == typeb.find():
                diag = diagnostic.Diagnostic("error",
                    "cannot unify {typea} with {typeb}",
                    {"typea": printer.name(typea), "typeb": printer.name(typeb)},
                    loca, highlights, notes)
            else: # give more detail
                diag = diagnostic.Diagnostic("error",
                    "cannot unify {typea} with {typeb}: {fraga} is incompatible with {fragb}",
                    {"typea": printer.name(typea),   "typeb": printer.name(typeb),
                     "fraga": printer.name(e.typea), "fragb": printer.name(e.typeb)},
                    loca, highlights, notes)
            self.engine.process(diag)

    # makenotes for the case where types of multiple elements are unified
    # with the type of parent expression
    def _makenotes_elts(self, elts, kind):
        def makenotes(printer, typea, typeb, loca, locb):
            return [
                diagnostic.Diagnostic("note",
                    "{kind} of type {typea}",
                    {"kind": kind, "typea": printer.name(elts[0].type)},
                    elts[0].loc),
                diagnostic.Diagnostic("note",
                    "{kind} of type {typeb}",
                    {"kind": kind, "typeb": printer.name(typeb)},
                    locb)
            ]
        return makenotes

    def visit_ListT(self, node):
        for elt in node.elts:
            self._unify(node.type["elt"], elt.type,
                        node.loc, elt.loc, self._makenotes_elts(node.elts, "a list element"))

    def visit_SubscriptT(self, node):
        # TODO: support more than just lists
        self._unify(builtins.TList(node.type), node.value.type,
                    node.loc, node.value.loc)

    def visit_IfExpT(self, node):
        self._unify(node.body.type, node.orelse.type,
                    node.body.loc, node.orelse.loc)
        node.type = node.body.type

    def visit_BoolOpT(self, node):
        for value in node.values:
            self._unify(node.type, value.type,
                        node.loc, value.loc, self._makenotes_elts(node.values, "an operand"))

    def visit_UnaryOpT(self, node):
        if isinstance(node.op, ast.Not):
            node.type = builtins.TBool()
        else:
            operand_type = node.operand.type.find()
            if builtins.is_numeric(operand_type):
                node.type = operand_type
            elif not types.is_var(operand_type):
                diag = diagnostic.Diagnostic("error",
                    "expected operand to be of numeric type, not {type}",
                    {"type": types.TypePrinter().name(operand_type)},
                    node.operand.loc)
                self.engine.process(diag)

    def visit_Assign(self, node):
        self.generic_visit(node)
        if len(node.targets) > 1:
            self._unify(builtins.TTuple([x.type for x in node.targets]), node.value.type,
                        node.targets[0].loc.join(node.targets[-1].loc), node.value.loc)
        else:
            self._unify(node.targets[0].type, node.value.type,
                        node.targets[0].loc, node.value.loc)

    def visit_AugAssign(self, node):
        self.generic_visit(node)
        self._unify(node.target.type, node.value.type,
                    node.target.loc, node.value.loc)

    def visit_For(self, node):
        old_in_loop, self.in_loop = self.in_loop, True
        self.generic_visit(node)
        self.in_loop = old_in_loop
        # TODO: support more than just lists
        self._unify(builtins.TList(node.target.type), node.iter.type,
                    node.target.loc, node.iter.loc)

    def visit_While(self, node):
        old_in_loop, self.in_loop = self.in_loop, True
        self.generic_visit(node)
        self.in_loop = old_in_loop

    def visit_Break(self, node):
        if not self.in_loop:
            diag = diagnostic.Diagnostic("error",
                "break statement outside of a loop", {},
                node.keyword_loc)
            self.engine.process(diag)

    def visit_Continue(self, node):
        if not self.in_loop:
            diag = diagnostic.Diagnostic("error",
                "continue statement outside of a loop", {},
                node.keyword_loc)
            self.engine.process(diag)

    def visit_FunctionDefT(self, node):
        old_function, self.function = self.function, node
        old_in_loop, self.in_loop = self.in_loop, False
        self.generic_visit(node)
        self.function = old_function
        self.in_loop = old_in_loop

    def visit_Return(self, node):
        if not self.function:
            diag = diagnostic.Diagnostic("error",
                "return statement outside of a function", {},
                node.keyword_loc)
            self.engine.process(diag)
            return

        self.generic_visit(node)
        def makenotes(printer, typea, typeb, loca, locb):
            return [
                diagnostic.Diagnostic("note",
                    "function with return type {typea}",
                    {"typea": printer.name(typea)},
                    self.function.name_loc),
                diagnostic.Diagnostic("note",
                    "a statement returning {typeb}",
                    {"typeb": printer.name(typeb)},
                    node.loc)
            ]
        if node.value is None:
            self._unify(self.function.return_type, builtins.TNone(),
                        self.function.name_loc, node.loc, makenotes)
        else:
            self._unify(self.function.return_type, node.value.type,
                        self.function.name_loc, node.value.loc, makenotes)

class Printer(algorithm.Visitor):
    """
    :class:`Printer` prints ``:`` and the node type after every typed node,
    and ``->`` and the node type before the colon in a function definition.

    In almost all cases (except function definition) this does not result
    in valid Python syntax.

    :ivar rewriter: (:class:`pythonparser.source.Rewriter`) rewriter instance
    """

    def __init__(self, buf):
        self.rewriter = source.Rewriter(buf)
        self.type_printer = types.TypePrinter()

    def rewrite(self):
        return self.rewriter.rewrite()

    def visit_FunctionDefT(self, node):
        super().generic_visit(node)

        self.rewriter.insert_before(node.colon_loc,
                                    "->{}".format(self.type_printer.name(node.return_type)))

    def generic_visit(self, node):
        super().generic_visit(node)

        if hasattr(node, "type"):
            self.rewriter.insert_after(node.loc,
                                       ":{}".format(self.type_printer.name(node.type)))

def main():
    import sys, fileinput, os

    if len(sys.argv) > 1 and sys.argv[1] == '+diag':
        del sys.argv[1]
        def process_diagnostic(diag):
            print("\n".join(diag.render(only_line=True)))
            if diag.level == 'fatal':
                exit()
    else:
        def process_diagnostic(diag):
            print("\n".join(diag.render()))
            if diag.level == 'fatal':
                exit(1)

    engine = diagnostic.Engine()
    engine.process = process_diagnostic

    buf = source.Buffer("".join(fileinput.input()), os.path.basename(fileinput.filename()))
    parsed, comments = parse_buffer(buf, engine=engine)
    typed = ASTTypedRewriter(engine=engine).visit(parsed)
    Inferencer(engine=engine).visit(typed)

    printer = Printer(buf)
    printer.visit(typed)
    for comment in comments:
        if comment.text.find("CHECK") >= 0:
            printer.rewriter.remove(comment.loc)
    print(printer.rewrite().source)


if __name__ == "__main__":
    main()
