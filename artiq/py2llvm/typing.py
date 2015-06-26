from pythonparser import source, ast, algorithm, diagnostic, parse_buffer
from collections import OrderedDict
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

        if len(self.env_stack) == 1:
            self.env_stack.append(self.typing_env)

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

    visit_Module       = visit_root # don't look at inner scopes
    visit_ClassDef     = visit_root
    visit_Lambda       = visit_root
    visit_DictComp     = visit_root
    visit_ListComp     = visit_root
    visit_SetComp      = visit_root
    visit_GeneratorExp = visit_root

    def visit_FunctionDef(self, node):
        if self.in_root:
            self._assignable(node.name)
        self.visit_root(node)

    def _assignable(self, name):
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
            self._assignable(name)
            self.env_stack[1][name] = self.typing_env[name]

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

    def __init__(self, engine, globals={}):
        self.engine = engine
        self.env_stack = [globals]

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
        return self.generic_visit(node)

    def visit_FunctionDef(self, node):
        extractor = LocalExtractor(env_stack=self.env_stack, engine=self.engine)
        extractor.visit(node)

        node = asttyped.FunctionDefT(
            typing_env=extractor.typing_env, globals_in_scope=extractor.global_,
            signature_type=self._find_name(node.name, node.name_loc), return_type=types.TVar(),
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
        return asttyped.TupleT(type=types.TTuple([x.type for x in node.elts]),
                               elts=node.elts, ctx=node.ctx, loc=node.loc)

    def visit_List(self, node):
        node = self.generic_visit(node)
        node = asttyped.ListT(type=builtins.TList(),
                              elts=node.elts, ctx=node.ctx, loc=node.loc)
        return self.visit(node)

    def visit_Attribute(self, node):
        node = self.generic_visit(node)
        node = asttyped.AttributeT(type=types.TVar(),
                                   value=node.value, attr=node.attr, ctx=node.ctx,
                                   dot_loc=node.dot_loc, attr_loc=node.attr_loc, loc=node.loc)
        return self.visit(node)

    def visit_Subscript(self, node):
        node = self.generic_visit(node)
        node = asttyped.SubscriptT(type=types.TVar(),
                                   value=node.value, slice=node.slice, ctx=node.ctx,
                                   loc=node.loc)
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
        node = asttyped.CallT(type=types.TVar(),
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

    def visit_Raise(self, node):
        node = self.generic_visit(node)
        if node.cause:
            diag = diagnostic.Diagnostic("error",
                "'raise from' syntax is not supported", {},
                node.from_loc)
            self.engine.process(diag)
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
    visit_Try = visit_unsupported


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
                        loca)
                ]
                if locb:
                    notes.append(
                        diagnostic.Diagnostic("note",
                            "expression of type {typeb}",
                            {"typeb": printer.name(typeb)},
                            locb))

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
        self.generic_visit(node)
        for elt in node.elts:
            self._unify(node.type["elt"], elt.type,
                        node.loc, elt.loc, self._makenotes_elts(node.elts, "a list element"))

    def visit_AttributeT(self, node):
        self.generic_visit(node)
        object_type = node.value.type.find()
        if not types.is_var(object_type):
            if node.attr in object_type.attributes:
                # assumes no free type variables in .attributes
                self._unify(node.type, object_type.attributes[node.attr],
                            node.loc, None)
            else:
                diag = diagnostic.Diagnostic("error",
                    "type {type} does not have an attribute '{attr}'",
                    {"type": types.TypePrinter().name(object_type), "attr": node.attr},
                    node.attr_loc, [node.value.loc])
                self.engine.process(diag)

    def _unify_collection(self, element, collection):
        # TODO: support more than just lists
        self._unify(builtins.TList(element.type), collection.type,
                    element.loc, collection.loc)

    def visit_SubscriptT(self, node):
        self.generic_visit(node)
        self._unify_collection(element=node, collection=node.value)

    def visit_IfExpT(self, node):
        self.generic_visit(node)
        self._unify(node.body.type, node.orelse.type,
                    node.body.loc, node.orelse.loc)
        self._unify(node.type, node.body.type,
                    node.loc, None)

    def visit_BoolOpT(self, node):
        self.generic_visit(node)
        for value in node.values:
            self._unify(node.type, value.type,
                        node.loc, value.loc, self._makenotes_elts(node.values, "an operand"))

    def visit_UnaryOpT(self, node):
        self.generic_visit(node)
        operand_type = node.operand.type.find()
        if isinstance(node.op, ast.Not):
            self._unify(node.type, builtins.TBool(),
                        node.loc, None)
        elif isinstance(node.op, ast.Invert):
            if builtins.is_int(operand_type):
                self._unify(node.type, operand_type,
                            node.loc, None)
            elif not types.is_var(operand_type):
                diag = diagnostic.Diagnostic("error",
                    "expected '~' operand to be of integer type, not {type}",
                    {"type": types.TypePrinter().name(operand_type)},
                    node.operand.loc)
                self.engine.process(diag)
        else: # UAdd, USub
            if builtins.is_numeric(operand_type):
                self._unify(node.type, operand_type,
                            node.loc, None)
            elif not types.is_var(operand_type):
                diag = diagnostic.Diagnostic("error",
                    "expected unary '{op}' operand to be of numeric type, not {type}",
                    {"op": node.op.loc.source(),
                     "type": types.TypePrinter().name(operand_type)},
                    node.operand.loc)
                self.engine.process(diag)

    def visit_CoerceT(self, node):
        self.generic_visit(node)
        if builtins.is_numeric(node.type) and builtins.is_numeric(node.expr.type):
            pass
        else:
            printer = types.TypePrinter()
            note = diagnostic.Diagnostic("note",
                "expression that required coercion to {typeb}",
                {"typeb": printer.name(node.type)},
                node.other_expr.loc)
            diag = diagnostic.Diagnostic("error",
                "cannot coerce {typea} to {typeb}",
                {"typea": printer.name(node.expr.type), "typeb": printer.name(node.type)},
                node.loc, notes=[note])
            self.engine.process(diag)

    def _coerce_one(self, typ, coerced_node, other_node):
        if coerced_node.type.find() == typ.find():
            return coerced_node
        elif isinstance(coerced_node, asttyped.CoerceT):
            node.type, node.other_expr = typ, other_node
        else:
            node = asttyped.CoerceT(type=typ, expr=coerced_node, other_expr=other_node,
                                    loc=coerced_node.loc)
        self.visit(node)
        return node

    def _coerce_numeric(self, nodes, map_return=lambda typ: typ):
        # See https://docs.python.org/3/library/stdtypes.html#numeric-types-int-float-complex.
        node_types = [node.type for node in nodes]
        if any(map(types.is_var, node_types)): # not enough info yet
            return
        elif not all(map(builtins.is_numeric, node_types)):
            err_node = next(filter(lambda node: not builtins.is_numeric(node.type), nodes))
            diag = diagnostic.Diagnostic("error",
                "cannot coerce {type} to a numeric type",
                {"type": types.TypePrinter().name(err_node.type)},
                err_node.loc, [])
            self.engine.process(diag)
            return
        elif any(map(builtins.is_float, node_types)):
            typ = builtins.TFloat()
        elif any(map(builtins.is_int, node_types)):
            widths = map(builtins.get_int_width, node_types)
            if all(widths):
                typ = builtins.TInt(types.TValue(max(widths)))
            else:
                typ = builtins.TInt()
        else:
            assert False

        return map_return(typ)

    def _order_by_pred(self, pred, left, right):
        if pred(left.type):
            return left, right
        elif pred(right.type):
            return right, left
        else:
            assert False

    def _coerce_binop(self, op, left, right):
        if isinstance(op, (ast.BitAnd, ast.BitOr, ast.BitXor,
                           ast.LShift, ast.RShift)):
            # bitwise operators require integers
            for operand in (left, right):
                if not types.is_var(operand.type) and not builtins.is_int(operand.type):
                    diag = diagnostic.Diagnostic("error",
                        "expected '{op}' operand to be of integer type, not {type}",
                        {"op": op.loc.source(),
                         "type": types.TypePrinter().name(operand.type)},
                        op.loc, [operand.loc])
                    self.engine.process(diag)
                    return

            return self._coerce_numeric((left, right), lambda typ: (typ, typ, typ))
        elif isinstance(op, ast.Add):
            # add works on numbers and also collections
            if builtins.is_collection(left.type) or builtins.is_collection(right.type):
                collection, other = \
                    self._order_by_pred(builtins.is_collection, left, right)
                if types.is_tuple(collection.type):
                    pred, kind = types.is_tuple, "tuple"
                elif builtins.is_list(collection.type):
                    pred, kind = builtins.is_list, "list"
                else:
                    assert False
                if not pred(other.type):
                    printer = types.TypePrinter()
                    note1 = diagnostic.Diagnostic("note",
                        "{kind} of type {typea}",
                        {"typea": printer.name(collection.type), "kind": kind},
                        collection.loc)
                    note2 = diagnostic.Diagnostic("note",
                        "{typeb}, which cannot be added to a {kind}",
                        {"typeb": printer.name(other.type), "kind": kind},
                        other.loc)
                    diag = diagnostic.Diagnostic("error",
                        "expected every '+' operand to be a {kind} in this context",
                        {"kind": kind},
                        op.loc, [other.loc, collection.loc],
                        [note1, note2])
                    self.engine.process(diag)
                    return

                if types.is_tuple(collection.type):
                    return types.TTuple(left.type.find().elts +
                                        right.type.find().elts), left.type, right.type
                elif builtins.is_list(collection.type):
                    self._unify(left.type, right.type,
                                left.loc, right.loc)
                    return left.type, left.type, right.type
            else:
                return self._coerce_numeric((left, right), lambda typ: (typ, typ, typ))
        elif isinstance(op, ast.Mult):
            # mult works on numbers and also number & collection
            if types.is_tuple(left.type) or types.is_tuple(right.type):
                tuple_, other = self._order_by_pred(types.is_tuple, left, right)
                diag = diagnostic.Diagnostic("error",
                    "py2llvm does not support passing tuples to '*'", {},
                    op.loc, [tuple_.loc])
                self.engine.process(diag)
                return
            elif builtins.is_list(left.type) or builtins.is_list(right.type):
                list_, other = self._order_by_pred(builtins.is_list, left, right)
                if not builtins.is_int(other.type):
                    printer = types.TypePrinter()
                    note1 = diagnostic.Diagnostic("note",
                        "list operand of type {typea}",
                        {"typea": printer.name(list_.type)},
                        list_.loc)
                    note2 = diagnostic.Diagnostic("note",
                        "operand of type {typeb}, which is not a valid repetition amount",
                        {"typeb": printer.name(other.type)},
                        other.loc)
                    diag = diagnostic.Diagnostic("error",
                        "expected '*' operands to be a list and an integer in this context", {},
                        op.loc, [list_.loc, other.loc],
                        [note1, note2])
                    self.engine.process(diag)
                    return

                return list_.type, left.type, right.type
            else:
                return self._coerce_numeric((left, right), lambda typ: (typ, typ, typ))
        elif isinstance(op, (ast.Div, ast.FloorDiv, ast.Mod, ast.Pow, ast.Sub)):
            # numeric operators work on any kind of number
            return self._coerce_numeric((left, right), lambda typ: (typ, typ, typ))
        else: # MatMult
            diag = diagnostic.Diagnostic("error",
                "operator '{op}' is not supported", {"op": op.loc.source()},
                op.loc)
            self.engine.process(diag)
            return

    def visit_BinOpT(self, node):
        self.generic_visit(node)
        coerced = self._coerce_binop(node.op, node.left, node.right)
        if coerced:
            return_type, left_type, right_type = coerced
            node.left  = self._coerce_one(left_type, node.left, other_node=node.right)
            node.right = self._coerce_one(right_type, node.right, other_node=node.left)
            self._unify(node.type, return_type,
                        node.loc, None)

    def visit_CompareT(self, node):
        self.generic_visit(node)
        pairs = zip([node.left] + node.comparators, node.comparators)
        if all(map(lambda op: isinstance(op, (ast.Is, ast.IsNot)), node.ops)):
            for left, right in pairs:
                self._unify(left.type, right.type,
                            left.loc, right.loc)
        elif all(map(lambda op: isinstance(op, (ast.In, ast.NotIn)), node.ops)):
            for left, right in pairs:
                self._unify_collection(element=left, collection=right)
        else: # Eq, NotEq, Lt, LtE, Gt, GtE
            operands = [node.left] + node.comparators
            operand_types = [operand.type for operand in operands]
            if any(map(builtins.is_collection, operand_types)):
                for left, right in pairs:
                    self._unify(left.type, right.type,
                                left.loc, right.loc)
            else:
                typ = self._coerce_numeric(operands)
                if typ:
                    try:
                        other_node = next(filter(lambda operand: operand.type.find() == typ.find(),
                                                 operands))
                    except StopIteration:
                        # can't find an argument with an exact type, meaning
                        # the return value is more generic than any of the inputs, meaning
                        # the type is known (typ is not None), but its width is not
                        def wide_enough(opreand):
                            return types.is_mono(opreand.type) and \
                                opreand.type.find().name == typ.find().name
                        other_node = next(filter(wide_enough, operands))
                    print(typ, other_node)
                    node.left, *node.comparators = \
                        [self._coerce_one(typ, operand, other_node) for operand in operands]
        self._unify(node.type, builtins.TBool(),
                    node.loc, None)

    def visit_ListCompT(self, node):
        self.generic_visit(node)
        self._unify(node.type, builtins.TList(node.elt.type),
                    node.loc, None)

    def visit_comprehension(self, node):
        self.generic_visit(node)
        self._unify_collection(element=node.target, collection=node.iter)

    def visit_builtin_call(self, node):
        typ = node.func.type.find()

        def valid_form(signature):
            return diagnostic.Diagnostic("note",
                "{func} can be invoked as: {signature}",
                {"func": typ.name, "signature": signature},
                node.func.loc)

        def diagnose(valid_forms):
            diag = diagnostic.Diagnostic("error",
                "{func} cannot be invoked with these arguments",
                {"func": typ.name},
                node.func.loc, notes=valid_forms)
            self.engine.process(diag)

        if builtins.is_builtin(typ, "class bool"):
            valid_forms = lambda: [
                valid_form("bool() -> bool"),
                valid_form("bool(x:'a) -> bool")
            ]

            if len(node.args) == 0 and len(node.keywords) == 0:
                pass # False
            elif len(node.args) == 1 and len(node.keywords) == 0:
                arg, = node.args
                pass # anything goes
            else:
                diagnose(valid_forms())

            self._unify(node.type, builtins.TBool(),
                        node.loc, None)
        elif builtins.is_builtin(typ, "class int"):
            valid_forms = lambda: [
                valid_form("int() -> int(width='a)"),
                valid_form("int(x:'a) -> int(width='b) where 'a is numeric"),
                valid_form("int(x:'a, width='b:<int literal>) -> int(width='b) where 'a is numeric")
            ]

            self._unify(node.type, builtins.TInt(),
                        node.loc, None)

            if len(node.args) == 0 and len(node.keywords) == 0:
                pass # 0
            elif len(node.args) == 1 and len(node.keywords) == 0 and \
                    builtins.is_numeric(node.args[0].type):
                pass
            elif len(node.args) == 1 and len(node.keywords) == 1 and \
                    builtins.is_numeric(node.args[0].type) and \
                    node.keywords[0].arg == 'width':
                width = node.keywords[0].value
                if not (isinstance(width, asttyped.NumT) and isinstance(width.n, int)):
                    diag = diagnostic.Diagnostic("error",
                        "the width argument of int() must be an integer literal", {},
                        node.keywords[0].loc)

                self._unify(node.type, builtins.TInt(types.TValue(width.n)),
                            node.loc, None)
            else:
                diagnose(valid_forms())
        elif builtins.is_builtin(typ, "class float"):
            valid_forms = lambda: [
                valid_form("float() -> float"),
                valid_form("float(x:'a) -> float where 'a is numeric")
            ]

            self._unify(node.type, builtins.TFloat(),
                        node.loc, None)

            if len(node.args) == 0 and len(node.keywords) == 0:
                pass # 0.0
            elif len(node.args) == 1 and len(node.keywords) == 0 and \
                    builtins.is_numeric(node.args[0].type):
                pass
            else:
                diagnose(valid_forms())
        elif builtins.is_builtin(typ, "class list"):
            valid_forms = lambda: [
                valid_form("list() -> list(elt='a)"),
                # TODO: add this form when adding iterators
                # valid_form("list(x) -> list(elt='a)")
            ]

            self._unify(node.type, builtins.TList(),
                        node.loc, None)

            if len(node.args) == 0 and len(node.keywords) == 0:
                pass # []
            else:
                diagnose(valid_forms())
        elif builtins.is_builtin(typ, "function len"):
            valid_forms = lambda: [
                valid_form("len(x:list(elt='a)) -> int(width='b)"),
            ]

            # TODO: should be ssize_t-sized
            self._unify(node.type, builtins.TInt(types.TValue(32)),
                        node.loc, None)

            if len(node.args) == 1 and len(node.keywords) == 0:
                arg, = node.args

                self._unify(arg.type, builtins.TList(),
                            arg.loc, None)
            else:
                diagnose(valid_forms())
        elif builtins.is_builtin(typ, "function round"):
            valid_forms = lambda: [
                valid_form("round(x:float) -> int(width='a)"),
            ]

            self._unify(node.type, builtins.TInt(),
                        node.loc, None)

            if len(node.args) == 1 and len(node.keywords) == 0:
                arg, = node.args

                self._unify(arg.type, builtins.TFloat(),
                            arg.loc, None)
            else:
                diagnose(valid_forms())
        # TODO: add when there are range types
        # elif builtins.is_builtin(typ, "function range"):
        #     valid_forms = lambda: [
        #         valid_form("range(max:'a) -> range(elt='a)"),
        #         valid_form("range(min:'a, max:'a) -> range(elt='a)"),
        #         valid_form("range(min:'a, max:'a, step:'a) -> range(elt='a)"),
        #     ]
        # TODO: add when it is clear what interface syscall() has
        # elif builtins.is_builtin(typ, "function syscall"):
        #     valid_Forms = lambda: [
        #     ]

    def visit_CallT(self, node):
        self.generic_visit(node)

        for (sigil_loc, vararg) in ((node.star_loc, node.starargs),
                                    (node.dstar_loc, node.kwargs)):
            if vararg:
                diag = diagnostic.Diagnostic("error",
                    "variadic arguments are not supported", {},
                    sigil_loc, [vararg.loc])
                self.engine.process(diag)
                return

        if types.is_var(node.func.type):
            return # not enough info yet
        elif types.is_mono(node.func.type) or types.is_builtin(node.func.type):
            return self.visit_builtin_call(node)
        elif not types.is_function(node.func.type):
            diag = diagnostic.Diagnostic("error",
                "cannot call this expression of type {type}",
                {"type": types.TypePrinter().name(node.func.type)},
                node.func.loc, [])
            self.engine.process(diag)
            return

        typ = node.func.type.find()
        passed_args = set()

        if len(node.args) > typ.arity():
            note = diagnostic.Diagnostic("note",
                "extraneous argument(s)", {},
                node.args[typ.arity()].loc.join(node.args[-1].loc))
            diag = diagnostic.Diagnostic("error",
                "this function of type {type} accepts at most {num} arguments",
                {"type": types.TypePrinter().name(node.func.type),
                 "num": typ.arity()},
                node.func.loc, [], [note])
            self.engine.process(diag)
            return

        for actualarg, (formalname, formaltyp) in \
                zip(node.args, list(typ.args.items()) + list(typ.optargs.items())):
            self._unify(actualarg.type, formaltyp,
                        actualarg.loc, None)
            passed_args.add(formalname)

        for keyword in node.keywords:
            if keyword.arg in passed_args:
                diag = diagnostic.Diagnostic("error",
                    "the argument '{name}' is already passed",
                    {"name": keyword.arg},
                    keyword.arg_loc)
                self.engine.process(diag)
                return

            if keyword.arg in typ.args:
                self._unify(keyword.value.type, typ.args[keyword.arg],
                            keyword.value.loc, None)
            elif keyword.arg in typ.optargs:
                self._unify(keyword.value.type, typ.optargs[keyword.arg],
                            keyword.value.loc, None)
            passed_args.add(keyword.arg)

        for formalname in typ.args:
            if formalname not in passed_args:
                note = diagnostic.Diagnostic("note",
                    "the called function is of type {type}",
                    {"type": types.TypePrinter().name(node.func.type)},
                    node.func.loc)
                diag = diagnostic.Diagnostic("error",
                    "mandatory argument '{name}' is not passed",
                    {"name": formalname},
                    node.begin_loc.join(node.end_loc), [], [note])
                self.engine.process(diag)
                return

        self._unify(node.type, typ.ret,
                    node.loc, None)

    def visit_LambdaT(self, node):
        self.generic_visit(node)
        signature_type = self._type_from_arguments(node.args, node.body.type)
        if signature_type:
            self._unify(node.type, signature_type,
                        node.loc, None)

    def visit_Assign(self, node):
        self.generic_visit(node)
        if len(node.targets) > 1:
            self._unify(types.TTuple([x.type for x in node.targets]), node.value.type,
                        node.targets[0].loc.join(node.targets[-1].loc), node.value.loc)
        else:
            self._unify(node.targets[0].type, node.value.type,
                        node.targets[0].loc, node.value.loc)

    def visit_AugAssign(self, node):
        self.generic_visit(node)
        coerced = self._coerce_binop(node.op, node.target, node.value)
        if coerced:
            return_type, target_type, value_type = coerced

            try:
                node.target.type.unify(target_type)
            except types.UnificationError as e:
                printer = types.TypePrinter()
                note = diagnostic.Diagnostic("note",
                    "expression of type {typec}",
                    {"typec": printer.name(node.value.type)},
                    node.value.loc)
                diag = diagnostic.Diagnostic("error",
                    "expression of type {typea} has to be coerced to {typeb}, "
                    "which makes assignment invalid",
                    {"typea": printer.name(node.target.type),
                     "typeb": printer.name(target_type)},
                    node.op.loc, [node.target.loc], [note])
                self.engine.process(diag)
                return

            try:
                node.target.type.unify(return_type)
            except types.UnificationError as e:
                printer = types.TypePrinter()
                note = diagnostic.Diagnostic("note",
                    "expression of type {typec}",
                    {"typec": printer.name(node.value.type)},
                    node.value.loc)
                diag = diagnostic.Diagnostic("error",
                    "the result of this operation has type {typeb}, "
                    "which makes assignment to a slot of type {typea} invalid",
                    {"typea": printer.name(node.target.type),
                     "typeb": printer.name(return_type)},
                    node.op.loc, [node.target.loc], [note])
                self.engine.process(diag)
                return

            node.value = self._coerce_one(value_type, node.value, other_node=node.target)

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

    def visit_withitem(self, node):
        self.generic_visit(node)
        if True: # none are supported yet
            diag = diagnostic.Diagnostic("error",
                "value of type {type} cannot act as a context manager",
                {"type": types.TypePrinter().name(node.context_expr.type)},
                node.context_expr.loc)
            self.engine.process(diag)

    def _type_from_arguments(self, node, ret):
        self.generic_visit(node)

        for (sigil_loc, vararg) in ((node.star_loc, node.vararg),
                                    (node.dstar_loc, node.kwarg)):
            if vararg:
                diag = diagnostic.Diagnostic("error",
                    "variadic arguments are not supported", {},
                    sigil_loc, [vararg.loc])
                self.engine.process(diag)
                return

        def extract_args(arg_nodes):
            args = [(arg_node.arg, arg_node.type) for arg_node in arg_nodes]
            return OrderedDict(args)

        return types.TFunction(extract_args(node.args[:len(node.args) - len(node.defaults)]),
                               extract_args(node.args[len(node.args) - len(node.defaults):]),
                               ret)

    def visit_arguments(self, node):
        self.generic_visit(node)
        for arg, default in zip(node.args[len(node.defaults):], node.defaults):
            self._unify(arg.type, default.type,
                        arg.loc, default.loc)

    def visit_FunctionDefT(self, node):
        old_function, self.function = self.function, node
        old_in_loop, self.in_loop = self.in_loop, False
        self.generic_visit(node)
        self.function = old_function
        self.in_loop = old_in_loop

        if any(node.decorator_list):
            diag = diagnostic.Diagnostic("error",
                "decorators are not supported", {},
                node.at_locs[0], [node.decorator_list[0].loc])
            self.engine.process(diag)
            return

        signature_type = self._type_from_arguments(node.args, node.return_type)
        if signature_type:
            self._unify(node.signature_type, signature_type,
                        node.name_loc, None)

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
    from . import prelude

    if len(sys.argv) > 1 and sys.argv[1] == '+diag':
        del sys.argv[1]
        def process_diagnostic(diag):
            print("\n".join(diag.render(only_line=True)))
            if diag.level == 'fatal':
                exit()
    else:
        def process_diagnostic(diag):
            print("\n".join(diag.render()))
            if diag.level in ('fatal', 'error'):
                exit(1)

    engine = diagnostic.Engine()
    engine.process = process_diagnostic

    buf = source.Buffer("".join(fileinput.input()).expandtabs(),
                        os.path.basename(fileinput.filename()))
    parsed, comments = parse_buffer(buf, engine=engine)
    typed = ASTTypedRewriter(globals=prelude.globals(), engine=engine).visit(parsed)
    Inferencer(engine=engine).visit(typed)

    printer = Printer(buf)
    printer.visit(typed)
    for comment in comments:
        if comment.text.find("CHECK") >= 0:
            printer.rewriter.remove(comment.loc)
    print(printer.rewrite().source)


if __name__ == "__main__":
    main()
