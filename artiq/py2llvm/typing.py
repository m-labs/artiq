from pythonparser import source, ast, algorithm, diagnostic, parse_buffer
from . import asttyped, types

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

    visit_ClassDef    = visit_root # don't look at inner scopes
    visit_FunctionDef = visit_root
    visit_Lambda      = visit_root
    visit_DictComp    = visit_root
    visit_ListComp    = visit_root
    visit_SetComp     = visit_root

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
                    "can't declare name '{name}' as nonlocal: it is not bound in any outer scope",
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


class Inferencer(algorithm.Transformer):
    def __init__(self, engine):
        self.engine = engine
        self.env_stack = []
        self.function  = None # currently visited function

    def _unify(self, typea, typeb, loca, locb, kind='generic'):
        try:
            typea.unify(typeb)
        except types.UnificationError as e:
            printer = types.TypePrinter()

            if kind == "expects":
                note1 = diagnostic.Diagnostic("note",
                    "expression expecting an operand of type {typea}",
                    {"typea": printer.name(typea)},
                    loca)
            elif kind == "return_type" or kind == "return_type_none":
                note1 = diagnostic.Diagnostic("note",
                    "function with return type {typea}",
                    {"typea": printer.name(typea)},
                    loca)
            else:
                note1 = diagnostic.Diagnostic("note",
                    "expression of type {typea}",
                    {"typea": printer.name(typea)},
                    loca)

            if kind == "return_type_none":
                note2 = diagnostic.Diagnostic("note",
                    "implied expression of type {typeb}",
                    {"typeb": printer.name(typeb)},
                    locb)
            else:
                note2 = diagnostic.Diagnostic("note",
                    "expression of type {typeb}",
                    {"typeb": printer.name(typeb)},
                    locb)

            if e.typea.find() == typea.find() and e.typeb.find() == typeb.find():
                diag = diagnostic.Diagnostic("fatal",
                    "cannot unify {typea} with {typeb}",
                    {"typea": printer.name(typea), "typeb": printer.name(typeb)},
                    loca, [locb], notes=[note1, note2])
            else: # give more detail
                diag = diagnostic.Diagnostic("fatal",
                    "cannot unify {typea} with {typeb}: {fraga} is incompatible with {fragb}",
                    {"typea": printer.name(typea),   "typeb": printer.name(typeb),
                     "fraga": printer.name(e.typea), "fragb": printer.name(e.typeb)},
                    loca, [locb], notes=[note1, note2])
            self.engine.process(diag)

    def _find_name(self, name, loc):
        for typing_env in reversed(self.env_stack):
            if name in typing_env:
                return typing_env[name]
        diag = diagnostic.Diagnostic("fatal",
            "name '{name}' is not bound to anything", {"name":name}, loc)
        self.engine.process(diag)

    def visit_root(self, node):
        extractor = LocalExtractor(env_stack=self.env_stack, engine=self.engine)
        extractor.visit(node)
        self.env_stack.append(extractor.typing_env)

        return self.visit(node)

    # Visitors that replace node with a typed node
    #
    def visit_arg(self, node):
        return asttyped.argT(type=self._find_name(node.arg, node.loc),
                             arg=node.arg, annotation=self.visit(node.annotation),
                             arg_loc=node.arg_loc, colon_loc=node.colon_loc, loc=node.loc)

    def visit_FunctionDef(self, node):
        extractor = LocalExtractor(env_stack=self.env_stack, engine=self.engine)
        extractor.visit(node)

        self.env_stack.append(extractor.typing_env)

        node = asttyped.FunctionDefT(
            typing_env=extractor.typing_env, globals_in_scope=extractor.global_,
            return_type=types.TVar(),

            name=node.name, args=node.args, returns=node.returns,
            body=node.body, decorator_list=node.decorator_list,
            keyword_loc=node.keyword_loc, name_loc=node.name_loc,
            arrow_loc=node.arrow_loc, colon_loc=node.colon_loc, at_locs=node.at_locs,
            loc=node.loc)

        old_function, self.function = self.function, node
        self.generic_visit(node)
        self.function = old_function

        self.env_stack.pop()

        return node

    def visit_Return(self, node):
        node = self.generic_visit(node)
        if node.value is None:
            self._unify(self.function.return_type, types.TNone(),
                        self.function.name_loc, node.value.loc, kind="return_type_none")
        else:
            self._unify(self.function.return_type, node.value.type,
                        self.function.name_loc, node.value.loc, kind="return_type")

    def visit_Num(self, node):
        if isinstance(node.n, int):
            typ = types.TInt()
        elif isinstance(node.n, float):
            typ = types.TFloat()
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
            typ = types.TBool()
        elif node.value is None:
            typ = types.TNone()
        return asttyped.NameConstantT(type=typ, value=node.value, loc=node.loc)

    def visit_Tuple(self, node):
        node = self.generic_visit(node)
        return asttyped.TupleT(type=types.TTuple([x.type for x in node.elts]),
                               elts=node.elts, ctx=node.ctx, loc=node.loc)

    def visit_List(self, node):
        node = self.generic_visit(node)
        node = asttyped.ListT(type=types.TList(),
                              elts=node.elts, ctx=node.ctx, loc=node.loc)
        for elt in node.elts:
            self._unify(node.type["elt"], elt.type,
                        node.loc, elt.loc, kind="expects")
        return node

    def visit_Subscript(self, node):
        node = self.generic_visit(node)
        node = asttyped.SubscriptT(type=types.TVar(),
                                   value=node.value, slice=node.slice, ctx=node.ctx,
                                   loc=node.loc)
        # TODO: support more than just lists
        self._unify(types.TList(node.type), node.value.type,
                    node.loc, node.value.loc, kind="expects")
        return node

    # Visitors that just unify types
    #
    def visit_Assign(self, node):
        node = self.generic_visit(node)
        if len(node.targets) > 1:
            self._unify(types.TTuple([x.type for x in node.targets]), node.value.type,
                        node.targets[0].loc.join(node.targets[-1].loc), node.value.loc)
        else:
            self._unify(node.targets[0].type, node.value.type,
                        node.targets[0].loc, node.value.loc)
        return node

    def visit_AugAssign(self, node):
        node = self.generic_visit(node)
        self._unify(node.target.type, node.value.type,
                    node.target.loc, node.value.loc)
        return node

    def visit_For(self, node):
        node = self.generic_visit(node)
        # TODO: support more than just lists
        self._unify(TList(node.target.type), node.iter.type,
                    node.target.loc, node.iter.loc)
        return node

    # Unsupported visitors
    #
    def visit_unsupported(self, node):
        diag = diagnostic.Diagnostic("fatal",
            "this syntax is not supported", {},
            node.loc)
        self.engine.process(diag)

    visit_Attribute = visit_unsupported
    visit_BinOp = visit_unsupported
    visit_BoolOp = visit_unsupported
    visit_Call = visit_unsupported
    visit_Compare = visit_unsupported
    visit_Dict = visit_unsupported
    visit_DictComp = visit_unsupported
    visit_Ellipsis = visit_unsupported
    visit_GeneratorExp = visit_unsupported
    visit_IfExp = visit_unsupported
    visit_Lambda = visit_unsupported
    visit_ListComp = visit_unsupported
    visit_Set = visit_unsupported
    visit_SetComp = visit_unsupported
    visit_Str = visit_unsupported
    visit_Starred = visit_unsupported
    visit_UnaryOp = visit_unsupported
    visit_Yield = visit_unsupported
    visit_YieldFrom = visit_unsupported

class Printer(algorithm.Visitor):
    def __init__(self, buf):
        self.rewriter = source.Rewriter(buf)
        self.type_printer = types.TypePrinter()

    def rewrite(self):
        return self.rewriter.rewrite()

    def visit_FunctionDefT(self, node):
        self.rewriter.insert_before(node.colon_loc,
                                    "->{}".format(self.type_printer.name(node.return_type)))

        super().generic_visit(node)

    def generic_visit(self, node):
        if hasattr(node, "type"):
            self.rewriter.insert_after(node.loc,
                                       ":{}".format(self.type_printer.name(node.type)))

        super().generic_visit(node)

def main():
    import sys, fileinput, os

    if sys.argv[1] == '+diag':
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
    typed = Inferencer(engine=engine).visit_root(parsed)
    printer = Printer(buf)
    printer.visit(typed)
    for comment in comments:
        if comment.text.find("CHECK") >= 0:
            printer.rewriter.remove(comment.loc)
    print(printer.rewrite().source)


if __name__ == "__main__":
    main()
