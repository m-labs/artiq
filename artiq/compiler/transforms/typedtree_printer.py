"""
:class:`TypedtreePrinter` prints a human-readable representation of typedtrees.
"""

from pythonparser import algorithm, ast
from .. import types, asttyped

class TypedtreePrinter(algorithm.Visitor):
    def __init__(self):
        self.str = None
        self.level = None
        self.last_nl = None
        self.type_printer = None

    def print(self, node):
        try:
            self.str = ""
            self.level = 0
            self.last_nl = 0
            self.type_printer = types.TypePrinter()
            self.visit(node)
            self._nl()
            return self.str
        finally:
            self.str = None
            self.level = None
            self.last_nl = 0
            self.type_printer = None

    def _nl(self):
        # self.str += "·"
        if len(self.str) != self.last_nl:
            self.str += "\n" + ("  " * self.level)
            self.last_nl = len(self.str)

    def _indent(self):
        self.level += 1
        self._nl()

    def _dedent(self):
        self._nl()
        self.level -= 1
        self.str = self.str[:-2]
        self.last_nl -= 2

    def visit(self, obj):
        if isinstance(obj, ast.AST):
            attrs = set(obj._fields) - {'ctx'}
            if isinstance(obj, asttyped.commontyped):
                attrs.update(set(obj._types))

            for attr in set(attrs):
                if not getattr(obj, attr):
                    attrs.remove(attr) # omit falsey stuff

            self.str += obj.__class__.__name__ + "("
            if len(attrs) > 1:
                self._indent()

            for attr in attrs:
                if len(attrs) > 1:
                    self._nl()
                self.str += attr + "="
                self.visit(getattr(obj, attr))
                if len(attrs) > 1:
                    self._nl()

            if len(attrs) > 1:
                self._dedent()
            self.str += ")"
        elif isinstance(obj, types.Type):
            self.str += self.type_printer.name(obj, max_depth=0)
        elif isinstance(obj, list):
            self.str += "["
            if len(obj) > 1:
                self._indent()

            for elem in obj:
                if len(obj) > 1:
                    self._nl()
                self.visit(elem)
                if len(obj) > 1:
                    self._nl()

            if len(obj) > 1:
                self._dedent()
            self.str += "]"
        else:
            self.str += repr(obj)
