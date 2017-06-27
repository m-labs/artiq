"""
:class:`ASTTypedRewriter` rewrites a parsetree (:mod:`pythonparser.ast`)
to a typedtree (:mod:`..asttyped`).
"""

from collections import OrderedDict
from pythonparser import ast, algorithm, diagnostic
from .. import asttyped, types, builtins

# This visitor will be called for every node with a scope,
# i.e.: class, function, comprehension, lambda
class LocalExtractor(algorithm.Visitor):
    def __init__(self, env_stack, engine):
        super().__init__()
        self.env_stack  = env_stack
        self.engine     = engine

        self.in_root    = False
        self.in_assign  = False
        self.typing_env = OrderedDict()

        # which names are global have to be recorded in the current scope
        self.global_    = set()

        # which names are nonlocal only affects whether the current scope
        # gets a new binding or not, so we throw this away
        self.nonlocal_  = set()

        # parameters can't be declared as global or nonlocal
        self.params     = set()

    def visit_in_assign(self, node, in_assign):
        try:
            old_in_assign, self.in_assign = self.in_assign, in_assign
            return self.visit(node)
        finally:
            self.in_assign = old_in_assign

    def visit_Assign(self, node):
        self.visit(node.value)
        self.visit_in_assign(node.targets, in_assign=True)

    def visit_For(self, node):
        self.visit(node.iter)
        self.visit_in_assign(node.target, in_assign=True)
        self.visit(node.body)
        self.visit(node.orelse)

    def visit_withitem(self, node):
        self.visit(node.context_expr)
        self.visit_in_assign(node.optional_vars, in_assign=True)

    def visit_comprehension(self, node):
        self.visit(node.iter)
        self.visit_in_assign(node.target, in_assign=True)
        self.visit(node.ifs)

    def visit_generator(self, node):
        if self.in_root:
            return
        self.in_root = True
        self.visit(list(reversed(node.generators)))
        self.visit(node.elt)

    visit_ListComp     = visit_generator
    visit_SetComp      = visit_generator
    visit_GeneratorExp = visit_generator

    def visit_DictComp(self, node):
        if self.in_root:
            return
        self.in_root = True
        self.visit(list(reversed(node.generators)))
        self.visit(node.key)
        self.visit(node.value)

    def visit_root(self, node):
        if self.in_root:
            return
        self.in_root = True
        self.generic_visit(node)

    visit_Module       = visit_root # don't look at inner scopes
    visit_ClassDef     = visit_root
    visit_Lambda       = visit_root

    def visit_FunctionDef(self, node):
        if self.in_root:
            self._assignable(node.name)
        self.visit_root(node)

    def _assignable(self, name):
        assert name is not None
        if name not in self.typing_env and name not in self.nonlocal_:
            self.typing_env[name] = types.TVar()

    def visit_arg(self, node):
        if node.arg in self.params:
            diag = diagnostic.Diagnostic("error",
                "duplicate parameter '{name}'", {"name": node.arg},
                node.loc)
            self.engine.process(diag)
            return
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

    def visit_Attribute(self, node):
        self.visit_in_assign(node.value, in_assign=False)

    def visit_Subscript(self, node):
        self.visit_in_assign(node.value, in_assign=False)
        self.visit_in_assign(node.slice, in_assign=False)

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
            if len(self.env_stack) == 1:
                self._assignable(name) # already in global scope
            else:
                if name not in self.env_stack[1]:
                    self.env_stack[1][name] = types.TVar()
                self.typing_env[name] = self.env_stack[1][name]

    def visit_Nonlocal(self, node):
        for name, loc in zip(node.names, node.name_locs):
            if self._check_not_in(name, self.global_, "global", "nonlocal", loc) or \
                    self._check_not_in(name, self.params, "a parameter", "nonlocal", loc):
                continue

            # nonlocal does not search prelude and global scopes
            found = False
            for outer_env in reversed(self.env_stack[2:]):
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
        if node.name is not None:
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

    def __init__(self, engine, prelude):
        self.engine = engine
        self.globals = None
        self.env_stack = [prelude]
        self.in_class = None

    def _try_find_name(self, name):
        if self.in_class is not None:
            typ = self.in_class.constructor_type.attributes.get(name)
            if typ is not None:
                return typ

        for typing_env in reversed(self.env_stack):
            if name in typing_env:
                return typing_env[name]

    def _find_name(self, name, loc):
        typ = self._try_find_name(name)
        if typ is not None:
            return typ

        diag = diagnostic.Diagnostic("fatal",
            "undefined variable '{name}'", {"name":name}, loc)
        self.engine.process(diag)

    # Visitors that replace node with a typed node
    #
    def visit_Module(self, node):
        extractor = LocalExtractor(env_stack=self.env_stack, engine=self.engine)
        extractor.visit(node)

        node = asttyped.ModuleT(
            typing_env=extractor.typing_env, globals_in_scope=extractor.global_,
            body=node.body, loc=node.loc)
        self.globals = node.typing_env

        try:
            self.env_stack.append(node.typing_env)
            return self.generic_visit(node)
        finally:
            self.env_stack.pop()

    def visit_FunctionDef(self, node):
        extractor = LocalExtractor(env_stack=self.env_stack, engine=self.engine)
        extractor.visit(node)

        signature_type = self._find_name(node.name, node.name_loc)

        node = asttyped.FunctionDefT(
            typing_env=extractor.typing_env, globals_in_scope=extractor.global_,
            signature_type=signature_type, return_type=types.TVar(),
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

    def visit_ClassDef(self, node):
        if any(node.bases) or any(node.keywords) or \
                node.starargs is not None or node.kwargs is not None:
            diag = diagnostic.Diagnostic("error",
                "inheritance is not supported", {},
                node.lparen_loc.join(node.rparen_loc))
            self.engine.process(diag)

        for child in node.body:
            if isinstance(child, (ast.Assign, ast.FunctionDef, ast.Pass)):
                continue

            diag = diagnostic.Diagnostic("fatal",
                "class body must contain only assignments and function definitions", {},
                child.loc)
            self.engine.process(diag)

        if node.name in self.env_stack[-1]:
            diag = diagnostic.Diagnostic("fatal",
                "variable '{name}' is already defined", {"name":node.name}, node.name_loc)
            self.engine.process(diag)

        extractor = LocalExtractor(env_stack=self.env_stack, engine=self.engine)
        extractor.visit(node)

        # Now we create two types.
        # The first type is the type of instances created by the constructor.
        # Its attributes are those of the class environment, but wrapped
        # appropriately so that they are linked to the class from which they
        # originate.
        instance_type = types.TInstance(node.name, OrderedDict())

        # The second type is the type of the constructor itself (in other words,
        # the class object): it is simply a singleton type that has the class
        # environment as attributes.
        constructor_type = types.TConstructor(instance_type)
        constructor_type.attributes = extractor.typing_env
        instance_type.constructor = constructor_type

        self.env_stack[-1][node.name] = constructor_type

        node = asttyped.ClassDefT(
            constructor_type=constructor_type,
            name=node.name,
            bases=self.visit(node.bases), keywords=self.visit(node.keywords),
            starargs=self.visit(node.starargs), kwargs=self.visit(node.kwargs),
            body=node.body,
            decorator_list=self.visit(node.decorator_list),
            keyword_loc=node.keyword_loc, name_loc=node.name_loc,
            lparen_loc=node.lparen_loc, star_loc=node.star_loc,
            dstar_loc=node.dstar_loc, rparen_loc=node.rparen_loc,
            colon_loc=node.colon_loc, at_locs=node.at_locs,
            loc=node.loc)

        try:
            old_in_class, self.in_class = self.in_class, node
            return self.generic_visit(node)
        finally:
            self.in_class = old_in_class

    def visit_arg(self, node):
        if node.annotation is not None:
            diag = diagnostic.Diagnostic("fatal",
                "type annotations are not supported here", {},
                node.annotation.loc)
            self.engine.process(diag)

        return asttyped.argT(type=self._find_name(node.arg, node.loc),
                             arg=node.arg, annotation=None,
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

    def visit_Str(self, node):
        if isinstance(node.s, str):
            typ = builtins.TStr()
        elif isinstance(node.s, bytes):
            typ = builtins.TBytes()
        else:
            assert False
        return asttyped.StrT(type=typ, s=node.s,
                             begin_loc=node.begin_loc, end_loc=node.end_loc, loc=node.loc)

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
        return asttyped.TupleT(type=types.TTuple([x.type for x in node.elts]),
                               elts=node.elts, ctx=node.ctx, loc=node.loc)

    def visit_List(self, node):
        node = self.generic_visit(node)
        node = asttyped.ListT(type=builtins.TList(),
                              elts=node.elts, ctx=node.ctx,
                              begin_loc=node.begin_loc, end_loc=node.end_loc, loc=node.loc)
        return self.visit(node)

    def visit_Attribute(self, node):
        node = self.generic_visit(node)
        node = asttyped.AttributeT(type=types.TVar(),
                                   value=node.value, attr=node.attr, ctx=node.ctx,
                                   dot_loc=node.dot_loc, attr_loc=node.attr_loc, loc=node.loc)
        return self.visit(node)

    def visit_Slice(self, node):
        node = self.generic_visit(node)
        node = asttyped.SliceT(type=types.TVar(),
                               lower=node.lower, upper=node.upper, step=node.step,
                               bound_colon_loc=node.bound_colon_loc,
                               step_colon_loc=node.step_colon_loc,
                               loc=node.loc)
        return self.visit(node)

    def visit_Subscript(self, node):
        node = self.generic_visit(node)
        node = asttyped.SubscriptT(type=types.TVar(),
                                   value=node.value, slice=node.slice, ctx=node.ctx,
                                   begin_loc=node.begin_loc, end_loc=node.end_loc, loc=node.loc)
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

    def visit_IfExp(self, node):
        node = self.generic_visit(node)
        node = asttyped.IfExpT(type=types.TVar(),
                               test=node.test, body=node.body, orelse=node.orelse,
                               if_loc=node.if_loc, else_loc=node.else_loc, loc=node.loc)
        return self.visit(node)

    def visit_ListComp(self, node):
        extractor = LocalExtractor(env_stack=self.env_stack, engine=self.engine)
        extractor.visit(node)

        node = asttyped.ListCompT(
            typing_env=extractor.typing_env, globals_in_scope=extractor.global_,
            type=types.TVar(),
            elt=node.elt, generators=node.generators,
            begin_loc=node.begin_loc, end_loc=node.end_loc, loc=node.loc)

        try:
            self.env_stack.append(node.typing_env)
            return self.generic_visit(node)
        finally:
            self.env_stack.pop()

    def visit_Call(self, node):
        node = self.generic_visit(node)
        node = asttyped.CallT(type=types.TVar(), iodelay=None, arg_exprs={},
                              func=node.func, args=node.args, keywords=node.keywords,
                              starargs=node.starargs, kwargs=node.kwargs,
                              star_loc=node.star_loc, dstar_loc=node.dstar_loc,
                              begin_loc=node.begin_loc, end_loc=node.end_loc, loc=node.loc)
        return node

    def visit_Lambda(self, node):
        extractor = LocalExtractor(env_stack=self.env_stack, engine=self.engine)
        extractor.visit(node)

        node = asttyped.LambdaT(
            typing_env=extractor.typing_env, globals_in_scope=extractor.global_,
            type=types.TVar(),
            args=node.args, body=node.body,
            lambda_loc=node.lambda_loc, colon_loc=node.colon_loc, loc=node.loc)

        try:
            self.env_stack.append(node.typing_env)
            return self.generic_visit(node)
        finally:
            self.env_stack.pop()

    def visit_ExceptHandler(self, node):
        node = self.generic_visit(node)
        if node.name is not None:
            name_type = self._find_name(node.name, node.name_loc)
        else:
            name_type = types.TVar()
        node = asttyped.ExceptHandlerT(
            name_type=name_type,
            filter=node.type, name=node.name, body=node.body,
            except_loc=node.except_loc, as_loc=node.as_loc, name_loc=node.name_loc,
            colon_loc=node.colon_loc, loc=node.loc)
        return node

    def visit_Raise(self, node):
        node = self.generic_visit(node)
        if node.cause:
            diag = diagnostic.Diagnostic("error",
                "'raise from' syntax is not supported", {},
                node.from_loc)
            self.engine.process(diag)
        return node

    def visit_For(self, node):
        node = self.generic_visit(node)
        node = asttyped.ForT(
            target=node.target, iter=node.iter, body=node.body, orelse=node.orelse,
            trip_count=None, trip_interval=None,
            keyword_loc=node.keyword_loc, in_loc=node.in_loc, for_colon_loc=node.for_colon_loc,
            else_loc=node.else_loc, else_colon_loc=node.else_colon_loc, loc=node.loc)
        return node

    def visit_withitem(self, node):
        node = self.generic_visit(node)
        node = asttyped.withitemT(
            context_expr=node.context_expr, optional_vars=node.optional_vars,
            enter_type=types.TVar(), exit_type=types.TVar(),
            as_loc=node.as_loc, loc=node.loc)
        return node

    # Unsupported visitors
    #
    def visit_unsupported(self, node):
        diag = diagnostic.Diagnostic("fatal",
            "this syntax is not supported", {},
            node.loc)
        self.engine.process(diag)

    # expr
    visit_Dict = visit_unsupported
    visit_DictComp = visit_unsupported
    visit_Ellipsis = visit_unsupported
    visit_GeneratorExp = visit_unsupported
    # visit_Set = visit_unsupported
    visit_SetComp = visit_unsupported
    visit_Starred = visit_unsupported
    visit_Yield = visit_unsupported
    visit_YieldFrom = visit_unsupported

    # stmt
    visit_Delete = visit_unsupported
    visit_Import = visit_unsupported
    visit_ImportFrom = visit_unsupported
