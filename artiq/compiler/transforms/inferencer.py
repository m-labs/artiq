"""
:class:`Inferencer` performs unification-based inference on a typedtree.
"""

from collections import OrderedDict
from pythonparser import algorithm, diagnostic, ast
from .. import asttyped, types, builtins

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
        self.has_return = False

    def _unify(self, typea, typeb, loca, locb, makenotes=None, when=""):
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
            if e.typea.find() == typea.find() and e.typeb.find() == typeb.find() or \
                    e.typeb.find() == typea.find() and e.typea.find() == typeb.find():
                diag = diagnostic.Diagnostic("error",
                    "cannot unify {typea} with {typeb}{when}",
                    {"typea": printer.name(typea), "typeb": printer.name(typeb),
                     "when": when},
                    loca, highlights, notes)
            else: # give more detail
                diag = diagnostic.Diagnostic("error",
                    "cannot unify {typea} with {typeb}{when}: {fraga} is incompatible with {fragb}",
                    {"typea": printer.name(typea),   "typeb": printer.name(typeb),
                     "fraga": printer.name(e.typea), "fragb": printer.name(e.typeb),
                      "when": when},
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
        elt_type_loc = node.loc
        for elt in node.elts:
            self._unify(node.type["elt"], elt.type,
                        elt_type_loc, elt.loc,
                        self._makenotes_elts(node.elts, "a list element"))
            elt_type_loc = elt.loc

    def visit_AttributeT(self, node):
        self.generic_visit(node)
        self._unify_attribute(result_type=node.type, value_node=node.value,
                              attr_name=node.attr, attr_loc=node.attr_loc,
                              loc=node.loc)

    def _unify_attribute(self, result_type, value_node, attr_name, attr_loc, loc):
        object_type = value_node.type.find()
        if not types.is_var(object_type):
            if attr_name in object_type.attributes:
                def makenotes(printer, typea, typeb, loca, locb):
                    return [
                        diagnostic.Diagnostic("note",
                            "expression of type {typea}",
                            {"typea": printer.name(typea)},
                            loca),
                        diagnostic.Diagnostic("note",
                            "expression of type {typeb}",
                            {"typeb": printer.name(object_type)},
                            value_node.loc)
                    ]

                attr_type = object_type.attributes[attr_name]
                if types.is_rpc_function(attr_type):
                    attr_type = types.instantiate(attr_type)

                self._unify(result_type, attr_type, loc, None,
                            makenotes=makenotes, when=" for attribute '{}'".format(attr_name))
            elif types.is_instance(object_type) and \
                    attr_name in object_type.constructor.attributes:
                attr_type = object_type.constructor.attributes[attr_name].find()
                if types.is_rpc_function(attr_type):
                    attr_type = types.instantiate(attr_type)

                if types.is_function(attr_type):
                    # Convert to a method.
                    if len(attr_type.args) < 1:
                        diag = diagnostic.Diagnostic("error",
                            "function '{attr}{type}' of class '{class}' cannot accept a self argument",
                            {"attr": attr_name, "type": types.TypePrinter().name(attr_type),
                             "class": object_type.name},
                            loc)
                        self.engine.process(diag)
                        return
                    else:
                        def makenotes(printer, typea, typeb, loca, locb):
                            if attr_loc is None:
                                msgb = "reference to an instance with a method '{attr}{typeb}'"
                            else:
                                msgb = "reference to a method '{attr}{typeb}'"

                            return [
                                diagnostic.Diagnostic("note",
                                    "expression of type {typea}",
                                    {"typea": printer.name(typea)},
                                    loca),
                                diagnostic.Diagnostic("note",
                                    msgb,
                                    {"attr": attr_name,
                                     "typeb": printer.name(attr_type)},
                                    locb)
                            ]

                        self._unify(object_type, list(attr_type.args.values())[0],
                                    value_node.loc, loc,
                                    makenotes=makenotes,
                                    when=" while inferring the type for self argument")

                    attr_type = types.TMethod(object_type, attr_type)

                if not types.is_var(attr_type):
                    self._unify(result_type, attr_type,
                                loc, None)
            else:
                if attr_loc.source_buffer == value_node.loc.source_buffer:
                    highlights, notes = [value_node.loc], []
                else:
                    # This happens when the object being accessed is embedded
                    # from the host program.
                    note = diagnostic.Diagnostic("note",
                        "object being accessed", {},
                        value_node.loc)
                    highlights, notes = [], [note]

                diag = diagnostic.Diagnostic("error",
                    "type {type} does not have an attribute '{attr}'",
                    {"type": types.TypePrinter().name(object_type), "attr": attr_name},
                    attr_loc, highlights, notes)
                self.engine.process(diag)

    def _unify_iterable(self, element, collection):
        if builtins.is_iterable(collection.type):
            rhs_type = collection.type.find()
            rhs_wrapped_lhs_type = types.TMono(rhs_type.name, {"elt": element.type})
            self._unify(rhs_wrapped_lhs_type, rhs_type,
                        element.loc, collection.loc)
        elif not types.is_var(collection.type):
            diag = diagnostic.Diagnostic("error",
                "type {type} is not iterable",
                {"type": types.TypePrinter().name(collection.type)},
                collection.loc, [])
            self.engine.process(diag)

    def visit_Index(self, node):
        self.generic_visit(node)
        value = node.value
        if types.is_tuple(value.type):
            diag = diagnostic.Diagnostic("error",
                "multi-dimensional slices are not supported", {},
                node.loc, [])
            self.engine.process(diag)
        else:
            self._unify(value.type, builtins.TInt(),
                        value.loc, None)

    def visit_SliceT(self, node):
        if (node.lower, node.upper, node.step) == (None, None, None):
            self._unify(node.type, builtins.TInt32(),
                        node.loc, None)
        else:
            self._unify(node.type, builtins.TInt(),
                        node.loc, None)
            for operand in (node.lower, node.upper, node.step):
                if operand is not None:
                    self._unify(operand.type, node.type,
                                operand.loc, None)

    def visit_ExtSlice(self, node):
        diag = diagnostic.Diagnostic("error",
            "multi-dimensional slices are not supported", {},
            node.loc, [])
        self.engine.process(diag)

    def visit_SubscriptT(self, node):
        self.generic_visit(node)
        if isinstance(node.slice, ast.Index):
            self._unify_iterable(element=node, collection=node.value)
        elif isinstance(node.slice, ast.Slice):
            self._unify(node.type, node.value.type,
                        node.loc, node.value.loc)
        else: # ExtSlice
            pass # error emitted above

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
        if builtins.is_numeric(node.type) and builtins.is_numeric(node.value.type):
            pass
        else:
            printer = types.TypePrinter()
            note = diagnostic.Diagnostic("note",
                "expression that required coercion to {typeb}",
                {"typeb": printer.name(node.type)},
                node.other_value.loc)
            diag = diagnostic.Diagnostic("error",
                "cannot coerce {typea} to {typeb}",
                {"typea": printer.name(node.value.type), "typeb": printer.name(node.type)},
                node.loc, notes=[note])
            self.engine.process(diag)

    def _coerce_one(self, typ, coerced_node, other_node):
        if coerced_node.type.find() == typ.find():
            return coerced_node
        elif isinstance(coerced_node, asttyped.CoerceT):
            node = coerced_node
            node.type, node.other_value = typ, other_node
        else:
            node = asttyped.CoerceT(type=typ, value=coerced_node, other_value=other_node,
                                    loc=coerced_node.loc)
        self.visit(node)
        return node

    def _coerce_numeric(self, nodes, map_return=lambda typ: typ):
        # See https://docs.python.org/3/library/stdtypes.html#numeric-types-int-float-complex.
        node_types = []
        for node in nodes:
            if isinstance(node, asttyped.CoerceT):
                node_types.append(node.value.type)
            else:
                node_types.append(node.type)
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
            widths = list(map(builtins.get_int_width, node_types))
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

                if types.is_var(other.type):
                    return

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
                    "passing tuples to '*' is not supported", {},
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
        elif isinstance(op, (ast.FloorDiv, ast.Mod, ast.Pow, ast.Sub)):
            # numeric operators work on any kind of number
            return self._coerce_numeric((left, right), lambda typ: (typ, typ, typ))
        elif isinstance(op, ast.Div):
            # division always returns a float
            return self._coerce_numeric((left, right),
                        lambda typ: (builtins.TFloat(), builtins.TFloat(), builtins.TFloat()))
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
                self._unify_iterable(element=left, collection=right)
        else: # Eq, NotEq, Lt, LtE, Gt, GtE
            operands = [node.left] + node.comparators
            operand_types = [operand.type for operand in operands]
            if any(map(builtins.is_collection, operand_types)):
                for left, right in pairs:
                    self._unify(left.type, right.type,
                                left.loc, right.loc)
            elif any(map(builtins.is_numeric, operand_types)):
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
                    node.left, *node.comparators = \
                        [self._coerce_one(typ, operand, other_node) for operand in operands]
            else:
                pass # No coercion required.
        self._unify(node.type, builtins.TBool(),
                    node.loc, None)

    def visit_ListCompT(self, node):
        if len(node.generators) > 1:
            diag = diagnostic.Diagnostic("error",
                "multiple for clauses in comprehensions are not supported", {},
                node.generators[1].for_loc)
            self.engine.process(diag)

        self.generic_visit(node)
        self._unify(node.type, builtins.TList(node.elt.type),
                    node.loc, None)

    def visit_comprehension(self, node):
        if any(node.ifs):
            diag = diagnostic.Diagnostic("error",
                "if clauses in comprehensions are not supported", {},
                node.if_locs[0])
            self.engine.process(diag)

        self.generic_visit(node)
        self._unify_iterable(element=node.target, collection=node.iter)

    def visit_builtin_call(self, node):
        typ = node.func.type.find()

        def valid_form(signature):
            return diagnostic.Diagnostic("note",
                "{func} can be invoked as: {signature}",
                {"func": typ.name, "signature": signature},
                node.func.loc)

        def diagnose(valid_forms):
            printer = types.TypePrinter()
            args  = [printer.name(arg.type) for arg in node.args]
            args += ["%s=%s" % (kw.arg, printer.name(kw.value.type)) for kw in node.keywords]

            diag = diagnostic.Diagnostic("error",
                "{func} cannot be invoked with the arguments ({args})",
                {"func": typ.name, "args": ", ".join(args)},
                node.func.loc, notes=valid_forms)
            self.engine.process(diag)

        def simple_form(info, arg_types=[], return_type=builtins.TNone()):
            self._unify(node.type, return_type,
                        node.loc, None)

            if len(node.args) == len(arg_types) and len(node.keywords) == 0:
                for index, arg_type in enumerate(arg_types):
                    self._unify(node.args[index].type, arg_type,
                                node.args[index].loc, None)
            else:
                diagnose([ valid_form(info) ])

        if types.is_exn_constructor(typ):
            valid_forms = lambda: [
                valid_form("{exn}() -> {exn}".format(exn=typ.name)),
                valid_form("{exn}(message:str) -> {exn}".format(exn=typ.name)),
                valid_form("{exn}(message:str, param1:int(width=64)) -> {exn}".format(exn=typ.name)),
                valid_form("{exn}(message:str, param1:int(width=64), "
                           "param2:int(width=64)) -> {exn}".format(exn=typ.name)),
                valid_form("{exn}(message:str, param1:int(width=64), "
                           "param2:int(width=64), param3:int(width=64)) "
                           "-> {exn}".format(exn=typ.name)),
            ]

            if len(node.args) == 0 and len(node.keywords) == 0:
                pass # Default message, zeroes as parameters
            elif len(node.args) >= 1 and len(node.args) <= 4 and len(node.keywords) == 0:
                message, *params = node.args

                self._unify(message.type, builtins.TStr(),
                            message.loc, None)
                for param in params:
                    self._unify(param.type, builtins.TInt64(),
                                param.loc, None)
            else:
                diagnose(valid_forms())

            self._unify(node.type, typ.instance,
                        node.loc, None)
        elif types.is_builtin(typ, "bool"):
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
        elif types.is_builtin(typ, "int"):
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
                    types.is_var(node.args[0].type):
                pass # undetermined yet
            elif len(node.args) == 1 and len(node.keywords) == 0 and \
                    builtins.is_numeric(node.args[0].type):
                self._unify(node.type, builtins.TInt(),
                            node.loc, None)
            elif len(node.args) == 1 and len(node.keywords) == 1 and \
                    builtins.is_numeric(node.args[0].type) and \
                    node.keywords[0].arg == 'width':
                width = node.keywords[0].value
                if not (isinstance(width, asttyped.NumT) and isinstance(width.n, int)):
                    diag = diagnostic.Diagnostic("error",
                        "the width argument of int() must be an integer literal", {},
                        node.keywords[0].loc)
                    self.engine.process(diag)
                    return

                self._unify(node.type, builtins.TInt(types.TValue(width.n)),
                            node.loc, None)
            else:
                diagnose(valid_forms())
        elif types.is_builtin(typ, "float"):
            valid_forms = lambda: [
                valid_form("float() -> float"),
                valid_form("float(x:'a) -> float where 'a is numeric")
            ]

            self._unify(node.type, builtins.TFloat(),
                        node.loc, None)

            if len(node.args) == 0 and len(node.keywords) == 0:
                pass # 0.0
            elif len(node.args) == 1 and len(node.keywords) == 0 and \
                    types.is_var(node.args[0].type):
                pass # undetermined yet
            elif len(node.args) == 1 and len(node.keywords) == 0 and \
                    builtins.is_numeric(node.args[0].type):
                pass
            else:
                diagnose(valid_forms())
        elif types.is_builtin(typ, "list"):
            valid_forms = lambda: [
                valid_form("list() -> list(elt='a)"),
                valid_form("list(x:'a) -> list(elt='b) where 'a is iterable")
            ]

            self._unify(node.type, builtins.TList(),
                        node.loc, None)

            if len(node.args) == 0 and len(node.keywords) == 0:
                pass # []
            elif len(node.args) == 1 and len(node.keywords) == 0:
                arg, = node.args

                if builtins.is_iterable(arg.type):
                    def makenotes(printer, typea, typeb, loca, locb):
                        return [
                            diagnostic.Diagnostic("note",
                                "iterator returning elements of type {typea}",
                                {"typea": printer.name(typea)},
                                loca),
                            diagnostic.Diagnostic("note",
                                "iterator returning elements of type {typeb}",
                                {"typeb": printer.name(typeb)},
                                locb)
                        ]
                    self._unify(node.type.find().params["elt"],
                                arg.type.find().params["elt"],
                                node.loc, arg.loc, makenotes=makenotes)
                elif types.is_var(arg.type):
                    pass # undetermined yet
                else:
                    note = diagnostic.Diagnostic("note",
                        "this expression has type {type}",
                        {"type": types.TypePrinter().name(arg.type)},
                        arg.loc)
                    diag = diagnostic.Diagnostic("error",
                        "the argument of list() must be of an iterable type", {},
                        node.func.loc, notes=[note])
                    self.engine.process(diag)
            else:
                diagnose(valid_forms())
        elif types.is_builtin(typ, "range"):
            valid_forms = lambda: [
                valid_form("range(max:int(width='a)) -> range(elt=int(width='a))"),
                valid_form("range(min:int(width='a), max:int(width='a)) "
                           "-> range(elt=int(width='a))"),
                valid_form("range(min:int(width='a), max:int(width='a), "
                           "step:int(width='a)) -> range(elt=int(width='a))"),
            ]

            range_elt = builtins.TInt(types.TVar())
            self._unify(node.type, builtins.TRange(range_elt),
                        node.loc, None)

            if len(node.args) in (1, 2, 3) and len(node.keywords) == 0:
                for arg in node.args:
                    self._unify(arg.type, range_elt,
                                arg.loc, None)
            else:
                diagnose(valid_forms())
        elif types.is_builtin(typ, "len"):
            valid_forms = lambda: [
                valid_form("len(x:'a) -> int(width='b) where 'a is iterable"),
            ]

            if len(node.args) == 1 and len(node.keywords) == 0:
                arg, = node.args

                if builtins.is_range(arg.type):
                    self._unify(node.type, builtins.get_iterable_elt(arg.type),
                                node.loc, None)
                elif builtins.is_list(arg.type):
                    # TODO: should be ssize_t-sized
                    self._unify(node.type, builtins.TInt32(),
                                node.loc, None)
                elif types.is_var(arg.type):
                    pass # undetermined yet
                else:
                    note = diagnostic.Diagnostic("note",
                        "this expression has type {type}",
                        {"type": types.TypePrinter().name(arg.type)},
                        arg.loc)
                    diag = diagnostic.Diagnostic("error",
                        "the argument of len() must be of an iterable type", {},
                        node.func.loc, notes=[note])
                    self.engine.process(diag)
            else:
                diagnose(valid_forms())
        elif types.is_builtin(typ, "round"):
            valid_forms = lambda: [
                valid_form("round(x:float) -> int(width='a)"),
                valid_form("round(x:float, width='b:<int literal>) -> int(width='b)")
            ]

            self._unify(node.type, builtins.TInt(),
                        node.loc, None)

            if len(node.args) == 1 and len(node.keywords) == 0:
                arg, = node.args

                self._unify(arg.type, builtins.TFloat(),
                            arg.loc, None)
            elif len(node.args) == 1 and len(node.keywords) == 1 and \
                    builtins.is_numeric(node.args[0].type) and \
                    node.keywords[0].arg == 'width':
                width = node.keywords[0].value
                if not (isinstance(width, asttyped.NumT) and isinstance(width.n, int)):
                    diag = diagnostic.Diagnostic("error",
                        "the width argument of round() must be an integer literal", {},
                        node.keywords[0].loc)
                    self.engine.process(diag)
                    return

                self._unify(node.type, builtins.TInt(types.TValue(width.n)),
                            node.loc, None)
            else:
                diagnose(valid_forms())
        elif types.is_builtin(typ, "print"):
            valid_forms = lambda: [
                valid_form("print(args...) -> None"),
            ]

            self._unify(node.type, builtins.TNone(),
                        node.loc, None)

            if len(node.keywords) == 0:
                # We can print any arguments.
                pass
            else:
                diagnose(valid_forms())
        elif types.is_builtin(typ, "rtio_log"):
            valid_forms = lambda: [
                valid_form("rtio_log(channel:str, args...) -> None"),
            ]

            self._unify(node.type, builtins.TNone(),
                        node.loc, None)

            if len(node.args) >= 1 and len(node.keywords) == 0:
                arg = node.args[0]

                self._unify(arg.type, builtins.TStr(),
                            arg.loc, None)
            else:
                diagnose(valid_forms())
        elif types.is_builtin(typ, "now"):
            simple_form("now() -> float",
                        [], builtins.TFloat())
        elif types.is_builtin(typ, "delay"):
            simple_form("delay(time:float) -> None",
                        [builtins.TFloat()])
        elif types.is_builtin(typ, "at"):
            simple_form("at(time:float) -> None",
                        [builtins.TFloat()])
        elif types.is_builtin(typ, "now_mu"):
            simple_form("now_mu() -> int(width=64)",
                        [], builtins.TInt64())
        elif types.is_builtin(typ, "delay_mu"):
            simple_form("delay_mu(time_mu:int(width=64)) -> None",
                        [builtins.TInt64()])
        elif types.is_builtin(typ, "at_mu"):
            simple_form("at_mu(time_mu:int(width=64)) -> None",
                        [builtins.TInt64()])
        elif types.is_builtin(typ, "mu_to_seconds"):
            simple_form("mu_to_seconds(time_mu:int(width=64)) -> float",
                        [builtins.TInt64()], builtins.TFloat())
        elif types.is_builtin(typ, "seconds_to_mu"):
            simple_form("seconds_to_mu(time:float) -> int(width=64)",
                        [builtins.TFloat()], builtins.TInt64())
        elif types.is_builtin(typ, "watchdog"):
            simple_form("watchdog(time:float) -> [builtin context manager]",
                        [builtins.TFloat()], builtins.TNone())
        elif types.is_constructor(typ):
            # An user-defined class.
            self._unify(node.type, typ.find().instance,
                        node.loc, None)
        else:
            assert False

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

        typ = node.func.type.find()

        if types.is_var(typ):
            return # not enough info yet
        elif types.is_builtin(typ):
            return self.visit_builtin_call(node)
        elif not (types.is_function(typ) or types.is_method(typ)):
            diag = diagnostic.Diagnostic("error",
                "cannot call this expression of type {type}",
                {"type": types.TypePrinter().name(typ)},
                node.func.loc, [])
            self.engine.process(diag)
            return

        if types.is_function(typ):
            typ_arity   = typ.arity()
            typ_args    = typ.args
            typ_optargs = typ.optargs
            typ_ret     = typ.ret
        else:
            typ = types.get_method_function(typ)
            if types.is_var(typ):
                return # not enough info yet

            typ_arity   = typ.arity() - 1
            typ_args    = OrderedDict(list(typ.args.items())[1:])
            typ_optargs = typ.optargs
            typ_ret     = typ.ret

        passed_args = dict()

        if len(node.args) > typ_arity:
            note = diagnostic.Diagnostic("note",
                "extraneous argument(s)", {},
                node.args[typ_arity].loc.join(node.args[-1].loc))
            diag = diagnostic.Diagnostic("error",
                "this function of type {type} accepts at most {num} arguments",
                {"type": types.TypePrinter().name(node.func.type),
                 "num": typ_arity},
                node.func.loc, [], [note])
            self.engine.process(diag)
            return

        for actualarg, (formalname, formaltyp) in \
                zip(node.args, list(typ_args.items()) + list(typ_optargs.items())):
            self._unify(actualarg.type, formaltyp,
                        actualarg.loc, None)
            passed_args[formalname] = actualarg.loc

        for keyword in node.keywords:
            if keyword.arg in passed_args:
                diag = diagnostic.Diagnostic("error",
                    "the argument '{name}' has been passed earlier as positional",
                    {"name": keyword.arg},
                    keyword.arg_loc, [passed_args[keyword.arg]])
                self.engine.process(diag)
                return

            if keyword.arg in typ_args:
                self._unify(keyword.value.type, typ_args[keyword.arg],
                            keyword.value.loc, None)
            elif keyword.arg in typ_optargs:
                self._unify(keyword.value.type, typ_optargs[keyword.arg],
                            keyword.value.loc, None)
            passed_args[keyword.arg] = keyword.arg_loc

        for formalname in typ_args:
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

        self._unify(node.type, typ_ret,
                    node.loc, None)

    def visit_LambdaT(self, node):
        self.generic_visit(node)
        signature_type = self._type_from_arguments(node.args, node.body.type)
        if signature_type:
            self._unify(node.type, signature_type,
                        node.loc, None)

    def visit_Assign(self, node):
        self.generic_visit(node)
        for target in node.targets:
            self._unify(target.type, node.value.type,
                        target.loc, node.value.loc)

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

    def visit_ForT(self, node):
        old_in_loop, self.in_loop = self.in_loop, True
        self.generic_visit(node)
        self.in_loop = old_in_loop
        self._unify_iterable(node.target, node.iter)

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

    def visit_withitemT(self, node):
        self.generic_visit(node)

        typ = node.context_expr.type
        if (types.is_builtin(typ, "interleave") or types.is_builtin(typ, "sequential") or
                (isinstance(node.context_expr, asttyped.CallT) and
                 types.is_builtin(node.context_expr.func.type, "watchdog"))):
            # builtin context managers
            if node.optional_vars is not None:
                self._unify(node.optional_vars.type, builtins.TNone(),
                            node.optional_vars.loc, None)
        elif types.is_instance(typ) or types.is_constructor(typ):
            # user-defined context managers
            self._unify_attribute(result_type=node.enter_type, value_node=node.context_expr,
                                  attr_name='__enter__', attr_loc=None, loc=node.loc)
            self._unify_attribute(result_type=node.exit_type, value_node=node.context_expr,
                                  attr_name='__exit__', attr_loc=None, loc=node.loc)

            printer = types.TypePrinter()

            def check_callback(attr_name, typ, arity):
                if types.is_var(typ):
                    return

                if not (types.is_method(typ) or types.is_function(typ)):
                    diag = diagnostic.Diagnostic("error",
                        "attribute '{attr}' of type {manager_type} must be a function",
                        {"attr": attr_name,
                         "manager_type": printer.name(node.context_expr.type)},
                        node.context_expr.loc)
                    self.engine.process(diag)
                    return

                if types.is_method(typ):
                    typ = types.get_method_function(typ).find()
                else:
                    typ = typ.find()

                if not (len(typ.args) == arity and len(typ.optargs) == 0):
                    diag = diagnostic.Diagnostic("error",
                        "function '{attr}{attr_type}' must accept "
                        "{arity} positional argument{s} and no optional arguments",
                        {"attr": attr_name,
                         "attr_type": printer.name(typ),
                         "arity": arity, "s": "s" if arity > 1 else ""},
                        node.context_expr.loc)
                    self.engine.process(diag)

                for formal_arg_name in list(typ.args)[1:]:
                    formal_arg_type = typ.args[formal_arg_name]
                    def makenotes(printer, typea, typeb, loca, locb):
                        return [
                            diagnostic.Diagnostic("note",
                                "exception handling via context managers is not supported; "
                                "the argument '{arg}' of function '{attr}{attr_type}' "
                                "will always be None",
                                {"arg": formal_arg_name,
                                 "attr": attr_name,
                                 "attr_type": printer.name(typ)},
                                loca),
                        ]

                    self._unify(formal_arg_type, builtins.TNone(),
                                node.context_expr.loc, None,
                                makenotes=makenotes)

            check_callback('__enter__', node.enter_type, 1)
            check_callback('__exit__', node.exit_type, 4)

            if node.optional_vars is not None:
                if types.is_method(node.exit_type):
                    var_type = types.get_method_function(node.exit_type).find().ret
                else:
                    var_type = node.exit_type.find().ret

                def makenotes(printer, typea, typeb, loca, locb):
                    return [
                        diagnostic.Diagnostic("note",
                            "expression of type {typea}",
                            {"typea": printer.name(typea)},
                            loca),
                        diagnostic.Diagnostic("note",
                            "context manager with an '__enter__' method returning {typeb}",
                            {"typeb": printer.name(typeb)},
                            locb)
                    ]

                self._unify(node.optional_vars.type, var_type,
                            node.optional_vars.loc, node.context_expr.loc,
                            makenotes=makenotes)

        elif not types.is_var(typ):
            diag = diagnostic.Diagnostic("error",
                "value of type {type} cannot act as a context manager",
                {"type": types.TypePrinter().name(typ)},
                node.context_expr.loc)
            self.engine.process(diag)

    def visit_With(self, node):
        self.generic_visit(node)

        for item_node in node.items:
            typ = item_node.context_expr.type.find()
            if (types.is_builtin(typ, "interleave") or types.is_builtin(typ, "sequential")) and \
                    len(node.items) != 1:
                diag = diagnostic.Diagnostic("error",
                    "the '{kind}' context manager must be the only one in a 'with' statement",
                    {"kind": typ.name},
                    node.keyword_loc.join(node.colon_loc))
                self.engine.process(diag)

    def visit_ExceptHandlerT(self, node):
        self.generic_visit(node)

        if node.filter is not None:
            if not types.is_exn_constructor(node.filter.type):
                diag = diagnostic.Diagnostic("error",
                    "this expression must refer to an exception constructor",
                    {"type": types.TypePrinter().name(node.filter.type)},
                    node.filter.loc)
                self.engine.process(diag)
            else:
                def makenotes(printer, typea, typeb, loca, locb):
                    return [
                        diagnostic.Diagnostic("note",
                            "expression of type {typea}",
                            {"typea": printer.name(typea)},
                            loca),
                        diagnostic.Diagnostic("note",
                            "constructor of an exception of type {typeb}",
                            {"typeb": printer.name(typeb)},
                            locb)
                    ]
                self._unify(node.name_type, node.filter.type.instance,
                            node.name_loc, node.filter.loc, makenotes)

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
        for arg, default in zip(node.args[len(node.args) - len(node.defaults):], node.defaults):
            self._unify(arg.type, default.type,
                        arg.loc, default.loc)

    def visit_FunctionDefT(self, node):
        for index, decorator in enumerate(node.decorator_list):
            if types.is_builtin(decorator.type, "kernel"):
                continue

            diag = diagnostic.Diagnostic("error",
                "decorators are not supported", {},
                node.at_locs[index], [])
            self.engine.process(diag)

        try:
            old_function, self.function = self.function, node
            old_in_loop, self.in_loop = self.in_loop, False
            old_has_return, self.has_return = self.has_return, False

            self.generic_visit(node)

            # Lack of return statements is not the only case where the return
            # type cannot be inferred. The other one is infinite (possibly mutual)
            # recursion. Since Python functions don't have to return a value,
            # we ignore that one.
            if not self.has_return:
                def makenotes(printer, typea, typeb, loca, locb):
                    return [
                        diagnostic.Diagnostic("note",
                            "function with return type {typea}",
                            {"typea": printer.name(typea)},
                            node.name_loc),
                    ]
                self._unify(node.return_type, builtins.TNone(),
                            node.name_loc, None, makenotes)
        finally:
            self.function = old_function
            self.in_loop = old_in_loop
            self.has_return = old_has_return

        signature_type = self._type_from_arguments(node.args, node.return_type)
        if signature_type:
            self._unify(node.signature_type, signature_type,
                        node.name_loc, None)

    def visit_ClassDefT(self, node):
        if any(node.decorator_list):
            diag = diagnostic.Diagnostic("error",
                "decorators are not supported", {},
                node.at_locs[0], [node.decorator_list[0].loc])
            self.engine.process(diag)

        self.generic_visit(node)

    def visit_Return(self, node):
        if not self.function:
            diag = diagnostic.Diagnostic("error",
                "return statement outside of a function", {},
                node.keyword_loc)
            self.engine.process(diag)
            return

        self.has_return = True

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

    def visit_Raise(self, node):
        self.generic_visit(node)

        if node.exc is not None:
            exc_type = node.exc.type
            if not types.is_var(exc_type) and not builtins.is_exception(exc_type):
                if types.is_exn_constructor(exc_type):
                    notes = [diagnostic.Diagnostic("note",
                        "this value is an exception constructor; use {suggestion} instead",
                        {"suggestion": node.exc.loc.source() + "()"},
                        node.exc.loc)]
                else:
                    notes = []

                diag = diagnostic.Diagnostic("error",
                    "cannot raise a value of type {type}, which is not an exception",
                    {"type": types.TypePrinter().name(exc_type)},
                    node.loc,
                    notes=notes)
                self.engine.process(diag)

    def visit_Assert(self, node):
        self.generic_visit(node)
        self._unify(node.test.type, builtins.TBool(),
                    node.test.loc, None)
        if node.msg is not None:
            if not isinstance(node.msg, asttyped.StrT):
                diag = diagnostic.Diagnostic("error",
                    "assertion message must be a string literal", {},
                    node.msg.loc)
                self.engine.process(diag)
