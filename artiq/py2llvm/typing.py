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

    def visit_AugAssign(self, node):
        self.visit_in_assign(node.target)
        self.visit(node.op)
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
            diag = diagnostic.Diagnostic('fatal',
                "name '{name}' cannot be {curkind} and {newkind} simultaneously",
                {"name": name, "curkind": curkind, "newkind": newkind}, loc)
            self.engine.process(diag)

    def visit_Global(self, node):
        for name, loc in zip(node.names, node.name_locs):
            self._check_not_in(name, self.nonlocal_, 'nonlocal', 'global', loc)
            self._check_not_in(name, self.params, 'a parameter', 'global', loc)
            self.global_.add(name)

    def visit_Nonlocal(self, node):
        for name, loc in zip(node.names, node.name_locs):
            self._check_not_in(name, self.global_, 'global', 'nonlocal', loc)
            self._check_not_in(name, self.params, 'a parameter', 'nonlocal', loc)

            found = False
            for outer_env in reversed(self.env_stack):
                if name in outer_env:
                    found = True
                    break
            if not found:
                diag = diagnostic.Diagnostic('fatal',
                    "can't declare name '{name}' as nonlocal: it is not bound in any outer scope",
                    {"name": name},
                    loc, [node.keyword_loc])
                self.engine.process(diag)

            self.nonlocal_.add(name)

    def visit_ExceptHandler(self, node):
        self.visit(node.type)
        self._assignable(node.name)
        for stmt in node.body:
            self.visit(stmt)


class Inferencer(algorithm.Transformer):
    def __init__(self, engine):
        self.engine = engine
        self.env_stack = [{}]

    def _unify(self, typea, typeb, loca, locb, kind):
        try:
            typea.unify(typeb)
        except types.UnificationError as e:
            if kind == 'generic':
                note1 = diagnostic.Diagnostic('note',
                    "expression of type {typea}",
                    {"typea": types.TypePrinter().name(typea)},
                    loca)
            elif kind == 'expects':
                note1 = diagnostic.Diagnostic('note',
                    "expression expecting an operand of type {typea}",
                    {"typea": types.TypePrinter().name(typea)},
                    loca)

            note2 = diagnostic.Diagnostic('note',
                "expression of type {typeb}",
                {"typeb": types.TypePrinter().name(typeb)},
                locb)

            if e.typea.find() == typea.find() and e.typeb.find() == typeb.find():
                diag = diagnostic.Diagnostic('fatal',
                    "cannot unify {typea} with {typeb}",
                    {"typea": types.TypePrinter().name(typea),
                     "typeb": types.TypePrinter().name(typeb)},
                    loca, [locb], notes=[note1, note2])
            else: # give more detail
                diag = diagnostic.Diagnostic('fatal',
                    "cannot unify {typea} with {typeb}: {fraga} is incompatible with {fragb}",
                    {"typea": types.TypePrinter().name(typea),
                     "typeb": types.TypePrinter().name(typeb),
                     "fraga": types.TypePrinter().name(e.typea),
                     "fragb": types.TypePrinter().name(e.typeb),},
                    loca, [locb], notes=[note1, note2])
            self.engine.process(diag)

    def visit_FunctionDef(self, node):
        extractor = LocalExtractor(env_stack=self.env_stack, engine=self.engine)
        extractor.visit(node)

        self.env_stack.append(extractor.typing_env)
        node = asttyped.FunctionDefT(
            typing_env=extractor.typing_env, globals_in_scope=extractor.global_,
            name=node.name, args=self.visit(node.args), returns=self.visit(node.returns),
            body=[self.visit(x) for x in node.body], decorator_list=node.decorator_list,
            keyword_loc=node.keyword_loc, name_loc=node.name_loc,
            arrow_loc=node.arrow_loc, colon_loc=node.colon_loc, at_locs=node.at_locs,
            loc=node.loc)
        self.generic_visit(node)
        self.env_stack.pop()

        return node

    def _find_name(self, name, loc):
        for typing_env in reversed(self.env_stack):
            if name in typing_env:
                return typing_env[name]
        diag = diagnostic.Diagnostic('fatal',
            "name '{name}' is not bound to anything", {"name":name}, loc)
        self.engine.process(diag)

    # Visitors that replace node with a typed node
    #
    def visit_arg(self, node):
        return asttyped.argT(type=self._find_name(node.arg, node.loc),
                             arg=node.arg, annotation=self.visit(node.annotation),
                             arg_loc=node.arg_loc, colon_loc=node.colon_loc, loc=node.loc)

    def visit_Num(self, node):
        if isinstance(node.n, int):
            typ = types.TInt()
        elif isinstance(node.n, float):
            typ = types.TFloat()
        else:
            diag = diagnostic.Diagnostic('fatal',
                "numeric type {type} is not supported", {"type": node.n.__class__.__name__},
                node.loc)
            self.engine.process(diag)
        return asttyped.NumT(type=typ,
                             n=node.n, loc=node.loc)

    def visit_Name(self, node):
        return asttyped.NameT(type=self._find_name(node.id, node.loc),
                              id=node.id, ctx=node.ctx, loc=node.loc)

    def visit_Tuple(self, node):
        node = self.generic_visit(node)
        return asttyped.TupleT(type=types.TTuple([x.type for x in node.elts]),
                               elts=node.elts, ctx=node.ctx, loc=node.loc)

    def visit_List(self, node):
        node = self.generic_visit(node)
        node = asttyped.ListT(type=types.TList(),
                              elts=node.elts, ctx=node.ctx, loc=node.loc)
        for elt in node.elts:
            self._unify(node.type['elt'], elt.type,
                        node.loc, elt.loc, kind='expects')
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

class Printer(algorithm.Visitor):
    def __init__(self, buf):
        self.rewriter = source.Rewriter(buf)
        self.type_printer = types.TypePrinter()

    def rewrite(self):
        return self.rewriter.rewrite()

    def generic_visit(self, node):
        if hasattr(node, 'type'):
            self.rewriter.insert_after(node.loc,
                                       ":%s" % self.type_printer.name(node.type))

        super().generic_visit(node)

def main():
    import sys, fileinput
    engine = diagnostic.Engine(all_errors_are_fatal=True)
    try:
        buf = source.Buffer("".join(fileinput.input()), fileinput.filename())
        parsed = parse_buffer(buf, engine=engine)
        typed = Inferencer(engine=engine).visit(parsed)
        printer = Printer(buf)
        printer.visit(typed)
        print(printer.rewrite().source)
    except diagnostic.Error as e:
        print("\n".join(e.diagnostic.render()), file=sys.stderr)

if __name__ == "__main__":
    main()
