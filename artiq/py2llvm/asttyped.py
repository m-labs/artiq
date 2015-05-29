"""
The typedtree module exports the PythonParser AST enriched with
typing information.
"""

from pythonparser import ast
from pythonparser.algorithm import Visitor as ASTVisitor

class commontyped(ast.commonloc):
    """A mixin for typed AST nodes."""

    _types = ('type',)

    def _reprfields(self):
        return self._fields + self._locs + self._types

class scoped(object):
    """
    :ivar typing_env: (dict with string keys and :class:`.types.Type` values)
        map of variable names to variable types
    :ivar globals_in_scope: (set of string keys)
        list of variables resolved as globals
    """

class ClassDefT(ast.ClassDef, scoped):
    pass

class FunctionDefT(ast.FunctionDef, scoped):
    pass

class LambdaT(ast.Lambda, scoped):
    pass

class DictCompT(ast.DictComp, scoped):
    pass

class ListCompT(ast.ListComp, scoped):
    pass

class SetCompT(ast.SetComp, scoped):
    pass

class argT(ast.arg, commontyped):
    pass

class NumT(ast.Num, commontyped):
    pass

class NameT(ast.Name, commontyped):
    pass

class NameConstantT(ast.NameConstant, commontyped):
    pass
