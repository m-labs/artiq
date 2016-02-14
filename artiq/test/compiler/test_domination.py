import unittest
from artiq.compiler.analyses.domination import DominatorTree, PostDominatorTree

class MockBasicBlock:
    def __init__(self, name):
        self.name = name
        self._successors = []
        self._predecessors = []

    def successors(self):
        return self._successors

    def predecessors(self):
        return self._predecessors

    def set_successors(self, successors):
        self._successors = list(successors)
        for block in self._successors:
            block._predecessors.append(self)

class MockFunction:
    def __init__(self, entry, basic_blocks):
        self._entry = entry
        self.basic_blocks = basic_blocks

    def entry(self):
        return self._entry

def makefn(entry_name, graph):
    blocks = {}
    for block_name in graph:
        blocks[block_name] = MockBasicBlock(block_name)
    for block_name in graph:
        successors = list(map(lambda name: blocks[name], graph[block_name]))
        blocks[block_name].set_successors(successors)
    return MockFunction(blocks[entry_name], blocks.values())

def dom(function, domtree):
    dom = {}
    for block in function.basic_blocks:
        dom[block.name] = [dom_block.name for dom_block in domtree.dominators(block)]
    return dom

def idom(function, domtree):
    idom = {}
    for block in function.basic_blocks:
        idom_block = domtree.immediate_dominator(block)
        idom[block.name] = idom_block.name if idom_block else None
    return idom

class TestDominatorTree(unittest.TestCase):
    def test_linear(self):
        func = makefn('A', {
            'A': ['B'],
            'B': ['C'],
            'C': []
        })
        domtree = DominatorTree(func)
        self.assertEqual({
            'C': 'B', 'B': 'A', 'A': 'A'
        }, idom(func, domtree))
        self.assertEqual({
            'C': ['C', 'B', 'A'], 'B': ['B', 'A'], 'A': ['A']
        }, dom(func, domtree))

    def test_diamond(self):
        func = makefn('A', {
            'A': ['C', 'B'],
            'B': ['D'],
            'C': ['D'],
            'D': []
        })
        domtree = DominatorTree(func)
        self.assertEqual({
            'D': 'A', 'C': 'A', 'B': 'A', 'A': 'A'
        }, idom(func, domtree))

    def test_combined(self):
        func = makefn('A', {
            'A': ['B', 'D'],
            'B': ['C'],
            'C': ['E'],
            'D': ['E'],
            'E': []
        })
        domtree = DominatorTree(func)
        self.assertEqual({
            'A': 'A', 'B': 'A', 'C': 'B', 'D': 'A', 'E': 'A'
        }, idom(func, domtree))

    def test_figure_2(self):
        func = makefn(5, {
            5: [3, 4],
            4: [1],
            3: [2],
            2: [1],
            1: [2]
        })
        domtree = DominatorTree(func)
        self.assertEqual({
            1: 5, 2: 5, 3: 5, 4: 5, 5: 5
        }, idom(func, domtree))

    def test_figure_4(self):
        func = makefn(6, {
            6: [4, 5],
            5: [1],
            4: [3, 2],
            3: [2],
            2: [1, 3],
            1: [2]
        })
        domtree = DominatorTree(func)
        self.assertEqual({
            1: 6, 2: 6, 3: 6, 4: 6, 5: 6, 6: 6
        }, idom(func, domtree))

class TestPostDominatorTree(unittest.TestCase):
    def test_linear(self):
        func = makefn('A', {
            'A': ['B'],
            'B': ['C'],
            'C': []
        })
        domtree = PostDominatorTree(func)
        self.assertEqual({
            'A': 'B', 'B': 'C', 'C': None
        }, idom(func, domtree))

    def test_diamond(self):
        func = makefn('A', {
            'A': ['B', 'D'],
            'B': ['C'],
            'C': ['E'],
            'D': ['E'],
            'E': []
        })
        domtree = PostDominatorTree(func)
        self.assertEqual({
            'E': None, 'D': 'E', 'C': 'E', 'B': 'C', 'A': 'E'
        }, idom(func, domtree))

    def test_multi_exit(self):
        func = makefn('A', {
            'A': ['B', 'C'],
            'B': [],
            'C': []
        })
        domtree = PostDominatorTree(func)
        self.assertEqual({
            'A': None, 'B': None, 'C': None
        }, idom(func, domtree))

    def test_multi_exit_diamond(self):
        func = makefn('A', {
            'A': ['B', 'C'],
            'B': ['D'],
            'C': ['D'],
            'D': ['E', 'F'],
            'E': [],
            'F': []
        })
        domtree = PostDominatorTree(func)
        self.assertEqual({
            'A': 'D', 'B': 'D', 'C': 'D', 'D': None, 'E': None, 'F': None
        }, idom(func, domtree))
