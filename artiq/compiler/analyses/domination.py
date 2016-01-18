"""
:class:`DominatorTree` computes the dominance relation over
control flow graphs.

See http://www.cs.rice.edu/~keith/EMBED/dom.pdf.
"""

class GenericDominatorTree:
    def __init__(self):
        self._assign_names()
        self._compute()

    def _traverse_in_postorder(self):
        raise NotImplementedError

    def _prev_block_names(self, block):
        raise NotImplementedError

    def _assign_names(self):
        postorder = self._traverse_in_postorder()

        self._start_name    = len(postorder) - 1
        self._block_of_name = postorder
        self._name_of_block = {}
        for block_name, block in enumerate(postorder):
            self._name_of_block[block] = block_name

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

        # Start block dominates itself.
        self._doms[self._start_name] = self._start_name

        # We don't yet know what blocks dominate all other blocks.
        for block_name in range(self._start_name):
            self._doms[block_name] = None

        changed = True
        while changed:
            changed = False

            # For all blocks except start block, in reverse postorder...
            for block_name in reversed(range(self._start_name)):
                # Select a new immediate dominator from the blocks we have
                # already processed, and remember all others.
                # We've already processed at least one previous block because
                # of the graph traverse order.
                new_idom, prev_block_names = None, []
                for prev_block_name in self._prev_block_names(block_name):
                    if new_idom is None and self._doms[prev_block_name] is not None:
                        new_idom = prev_block_name
                    else:
                        prev_block_names.append(prev_block_name)

                # Find a common previous block
                for prev_block_name in prev_block_names:
                    if self._doms[prev_block_name] is not None:
                        new_idom = self._intersect(prev_block_name, new_idom)

                if self._doms[block_name] != new_idom:
                    self._doms[block_name] = new_idom
                    changed = True

    def immediate_dominator(self, block):
        return self._block_of_name[self._doms[self._name_of_block[block]]]

    def dominators(self, block):
        # Blocks that are statically unreachable from entry are considered
        # dominated by every other block.
        if block not in self._name_of_block:
            yield from self._block_of_name
            return

        block_name = self._name_of_block[block]
        yield self._block_of_name[block_name]
        while block_name != self._doms[block_name]:
            block_name = self._doms[block_name]
            yield self._block_of_name[block_name]

class DominatorTree(GenericDominatorTree):
    def __init__(self, function):
        self.function = function
        super().__init__()

    def _traverse_in_postorder(self):
        postorder = []

        visited = set()
        def visit(block):
            visited.add(block)
            for next_block in block.successors():
                if next_block not in visited:
                    visit(next_block)
            postorder.append(block)

        visit(self.function.entry())

        return postorder

    def _prev_block_names(self, block_name):
        for block in self._block_of_name[block_name].predecessors():
            # Only return predecessors that are statically reachable from entry.
            if block in self._name_of_block:
                yield self._name_of_block[block]

class PostDominatorTree(GenericDominatorTree):
    def __init__(self, function):
        self.function = function
        super().__init__()

    def _traverse_in_postorder(self):
        postorder = []

        visited = set()
        def visit(block):
            visited.add(block)
            for next_block in block.predecessors():
                if next_block not in visited:
                    visit(next_block)
            postorder.append(block)

        for block in self.function.basic_blocks:
            if not any(block.successors()):
                visit(block)

        postorder.append(None) # virtual exit block
        return postorder

    def _prev_block_names(self, block_name):
        succ_blocks = self._block_of_name[block_name].successors()
        if len(succ_blocks) > 0:
            for block in succ_blocks:
                yield self._name_of_block[block]
        else:
            yield self._start_name
