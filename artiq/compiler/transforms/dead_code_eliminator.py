"""
:class:`DeadCodeEliminator` is a very simple dead code elimination
transform: it only removes basic blocks with no predecessors.
"""

from .. import ir

class DeadCodeEliminator:
    def __init__(self, engine):
        self.engine = engine

    def process(self, functions):
        for func in functions:
            self.process_function(func)

    def process_function(self, func):
        for block in func.basic_blocks:
            if not any(block.predecessors()) and block != func.entry():
                block.erase()
