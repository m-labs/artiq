"""
The typedtree module exports the PythonParser AST enriched with
typing information.
"""

from pythonparser import ast
from pythonparser.algorithm import Visitor as ASTVisitor

class commontyped(ast.commonloc):
    """A mixin for typed AST nodes."""

    _types = ("type",)

    def _reprfields(self):
        return self._fields + self._locs + self._types

class scoped(object):
    """
    :ivar typing_env: (dict with string keys and :class:`.types.Type` values)
        map of variable names to variable types
    :ivar globals_in_scope: (set of string keys)
        list of variables resolved as globals
    """

# Typed versions of untyped nodes
class argT(ast.arg, commontyped):
    pass

class ClassDefT(ast.ClassDef, scoped):
    pass
class FunctionDefT(ast.FunctionDef, scoped):
    pass
class ModuleT(ast.Module, scoped):
    pass

class AttributeT(ast.Attribute, commontyped):
    pass
class BinOpT(ast.BinOp, commontyped):
    pass
class BoolOpT(ast.BoolOp, commontyped):
    pass
class CallT(ast.Call, commontyped):
    pass
class CompareT(ast.Compare, commontyped):
    pass
class DictT(ast.Dict, commontyped):
    pass
class DictCompT(ast.DictComp, commontyped, scoped):
    pass
class EllipsisT(ast.Ellipsis, commontyped):
    pass
class GeneratorExpT(ast.GeneratorExp, commontyped, scoped):
    pass
class IfExpT(ast.IfExp, commontyped):
    pass
class LambdaT(ast.Lambda, commontyped, scoped):
    pass
class ListT(ast.List, commontyped):
    pass
class ListCompT(ast.ListComp, commontyped, scoped):
    pass
class NameT(ast.Name, commontyped):
    pass
class NameConstantT(ast.NameConstant, commontyped):
    pass
class NumT(ast.Num, commontyped):
    pass
class SetT(ast.Set, commontyped):
    pass
class SetCompT(ast.SetComp, commontyped, scoped):
    pass
class StrT(ast.Str, commontyped):
    pass
class StarredT(ast.Starred, commontyped):
    pass
class SubscriptT(ast.Subscript, commontyped):
    pass
class TupleT(ast.Tuple, commontyped):
    pass
class UnaryOpT(ast.UnaryOp, commontyped):
    pass
class YieldT(ast.Yield, commontyped):
    pass
class YieldFromT(ast.YieldFrom, commontyped):
    pass

# Novel typed nodes
class CoerceT(ast.expr, commontyped):
    _fields = ('expr',) # other_expr deliberately not in _fields
