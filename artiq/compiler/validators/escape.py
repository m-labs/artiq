"""
:class:`EscapeValidator` verifies that no mutable data escapes
the region of its allocation.
"""

from pythonparser import algorithm, diagnostic
from .. import asttyped, types, builtins

class EscapeValidator(algorithm.Visitor):
    pass
