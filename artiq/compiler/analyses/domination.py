"""
:class:`DominatorTree` computes the dominance relation over
control flow graphs.

See http://www.cs.colostate.edu/~mstrout/CS553/slides/lecture04.pdf.
"""

from functools import reduce, cmp_to_key

# Key Idea
#   If a node dominates all
#   predecessors of node n, then it
#   also dominates node n
class DominatorTree:
    def __init__(self, func):
        entry = func.get_entry()

        self.dominated_by = { entry: {entry} }
        for block in func.basic_blocks:
            if block != entry:
                self.dominated_by[block] = set(func.basic_blocks)

        predecessors = {block: block.predecessors() for block in func.basic_blocks}
        while True:
            changed = False

            for block in func.basic_blocks:
                if block == entry:
                    continue

                if not any(predecessors[block]):
                    # Unreachable blocks are dominated by everything
                    continue

                new_dominated_by = {block}.union(
                    reduce(lambda a, b: a.intersection(b),
                           (self.dominated_by[pred] for pred in predecessors[block])))
                if new_dominated_by != self.dominated_by[block]:
                    self.dominated_by[block] = new_dominated_by
                    changed = True

            if not changed:
                break

    def in_domination_order(self):
        blocks = list(self.dominated_by.keys())
        blocks.sort(key=cmp_to_key(lambda a, b: a in self.dominated_by[b]))
        return blocks
