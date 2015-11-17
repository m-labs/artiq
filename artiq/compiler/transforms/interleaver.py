"""
:class:`Interleaver` reorders requests to the RTIO core so that
the timestamp would always monotonically nondecrease.
"""

from .. import ir
from ..analyses import domination

class Interleaver:
    def __init__(self, engine):
        self.engine = engine

    def process(self, functions):
        for func in functions:
            self.process_function(func)

    def process_function(self, func):
        domtree = domination.PostDominatorTree(func)
        print(func)
        for block in func.basic_blocks:
            idom = domtree.immediate_dominator(block)
            print(block.name, "->", idom.name if idom else "<exit>")
