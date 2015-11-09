"""
:class:`DominatorTree` computes the dominance relation over
control flow graphs.

See http://www.cs.rice.edu/~keith/EMBED/dom.pdf.
"""

class GenericDominatorTree:
    def __init__(self):
        self._assign_names()
        self._compute()

    def _start_blocks(self):
        """
        Returns a starting collection of basic blocks (entry block
        for dominator tree and exit blocks for postdominator tree).
        """
        raise NotImplementedError

    def _next_blocks(self, block):
        """
        Returns the collection of blocks to be traversed after `block`
        (successors for dominator tree and predecessors for postdominator
        tree).
        """
        raise NotImplementedError

    def _prev_blocks(self, block):
        """
        Returns the collection of blocks to be traversed before `block`
        (predecessors for dominator tree and successors for postdominator
        tree).
        """
        raise NotImplementedError

    def _assign_names(self):
        """Assigns names to basic blocks in postorder."""
        visited = set()
        postorder = []

        def visit(block):
            visited.add(block)
            for next_block in self._next_blocks(block):
                if next_block not in visited:
                    visit(next_block)
            postorder.append(block)

        for block in self._start_blocks():
            visit(block)

        self._last_name     = len(postorder)
        self._block_of_name = postorder
        self._name_of_block = {}
        for block_name, block in enumerate(postorder):
            # print("name", block_name + 1, block.name)
            self._name_of_block[block] = block_name

    def _start_block_names(self):
        for block in self._start_blocks():
            yield self._name_of_block[block]

    def _next_block_names(self, block_name):
        for block in self._next_blocks(self._block_of_name[block_name]):
            yield self._name_of_block[block]

    def _prev_block_names(self, block_name):
        for block in self._prev_blocks(self._block_of_name[block_name]):
            yield self._name_of_block[block]

    def _intersect(self, block_name_1, block_name_2):
        finger_1, finger_2 = block_name_1, block_name_2
        while finger_1 != finger_2:
            while finger_1 < finger_2:
                finger_1 = self._doms[finger_1]
            while finger_2 < finger_1:
                finger_2 = self._doms[finger_2]
        return finger_1

    def _compute(self):
        self._doms = {}

        for block_name in range(self._last_name):
            self._doms[block_name] = None

        start_block_names = set()
        for block_name in self._start_block_names():
            self._doms[block_name] = block_name
            start_block_names.add(block_name)

        changed = True
        while changed:
            # print("doms", {k+1: self._doms[k]+1 if self._doms[k] is not None else None for k in self._doms})

            changed = False
            for block_name in reversed(range(self._last_name)):
                if block_name in start_block_names:
                    continue

                new_idom, prev_block_names = None, []
                for prev_block_name in self._prev_block_names(block_name):
                    if new_idom is None and self._doms[prev_block_name] is not None:
                        new_idom = prev_block_name
                    else:
                        prev_block_names.append(prev_block_name)

                # print("block_name", block_name + 1, "new_idom", new_idom + 1)
                for prev_block_name in prev_block_names:
                    # print("prev_block_name", prev_block_name + 1)
                    if self._doms[prev_block_name] is not None:
                        new_idom = self._intersect(prev_block_name, new_idom)
                        # print("new_idom+", new_idom + 1)

                if self._doms[block_name] != new_idom:
                    self._doms[block_name] = new_idom
                    changed = True

    def immediate_dominator(self, block):
        return self._block_of_name[self._doms[self._name_of_block[block]]]

    def dominators(self, block):
        yield block

        block_name = self._name_of_block[block]
        while block_name != self._doms[block_name]:
            block_name = self._doms[block_name]
            yield self._block_of_name[block_name]

class DominatorTree(GenericDominatorTree):
    def __init__(self, function):
        self.function = function
        super().__init__()

    def _start_blocks(self):
        return [self.function.entry()]

    def _next_blocks(self, block):
        return block.successors()

    def _prev_blocks(self, block):
        return block.predecessors()

class PostDominatorTree(GenericDominatorTree):
    def __init__(self, function):
        self.function = function
        super().__init__()

    def _start_blocks(self):
        return [block for block in self.function.basic_blocks
                       if none(block.successors())]

    def _next_blocks(self, block):
        return block.predecessors()

    def _prev_blocks(self, block):
        return block.successors()
