"""
:class:`LocalAccessValidator` verifies that local variables
are not accessed before being used.
"""

from functools import reduce
from pythonparser import diagnostic
from .. import ir, analyses

def is_special_variable(name):
    return "$" in name

class LocalAccessValidator:
    def __init__(self, engine):
        self.engine = engine

    def process(self, functions):
        for func in functions:
            self.process_function(func)

    def process_function(self, func):
        # Find all environments and closures allocated in this func.
        environments, closures = [], []
        for insn in func.instructions():
            if isinstance(insn, ir.Alloc) and ir.is_environment(insn.type):
                environments.append(insn)
            elif isinstance(insn, ir.Closure):
                closures.append(insn)

        # Compute initial state of interesting environments.
        # Environments consisting only of internal variables (containing a ".")
        # are ignored.
        initial_state = {}
        for env in environments:
            env_state = {var: False for var in env.type.params if "." not in var}
            if any(env_state):
                initial_state[env] = env_state

        # Traverse the acyclic graph made of basic blocks and forward edges only,
        # while updating the environment state.
        domtree = analyses.DominatorTree(func)
        state   = {}
        def traverse(block):
            # Have we computed the state of this block already?
            if block in state:
                return state[block]

            # No! Which forward edges lead to this block?
            # If we dominate a predecessor, it's a back edge instead.
            forward_edge_preds = [pred for pred in block.predecessors()
                                        if block not in domtree.dominators(pred)]

            # Figure out what the state is before the leader
            # instruction of this block.
            pred_states = [traverse(pred) for pred in forward_edge_preds]
            block_state = {}
            if len(pred_states) > 1:
                for env in initial_state:
                    # The variable has to be initialized in all predecessors
                    # in order to be initialized in this block.
                    def merge_state(a, b):
                        return {var: a[var] and b[var] for var in a}
                    block_state[env] = reduce(merge_state,
                                              [state[env] for state in pred_states])
            elif len(pred_states) == 1:
                # The state is the same as at the terminator of predecessor.
                # We'll mutate it, so copy.
                pred_state = pred_states[0]
                for env in initial_state:
                    env_state = pred_state[env]
                    block_state[env] = {var: env_state[var] for var in env_state}
            else:
                # This is the entry block.
                for env in initial_state:
                    env_state = initial_state[env]
                    block_state[env] = {var: env_state[var] for var in env_state}

            # Update the state based on block contents, while validating
            # that no access to uninitialized variables will be done.
            for insn in block.instructions:
                def pred_at_fault(env, var_name):
                    # Find out where the uninitialized state comes from.
                    for pred, pred_state in zip(forward_edge_preds, pred_states):
                        if not pred_state[env][var_name]:
                            return pred

                    # It's the entry block and it was never initialized.
                    return None

                set_local_in_this_frame = False
                if (isinstance(insn, (ir.SetLocal, ir.GetLocal)) and
                        not is_special_variable(insn.var_name)):
                    env, var_name = insn.environment(), insn.var_name

                    # Make sure that the variable is defined in the scope of this function.
                    if env in block_state and var_name in block_state[env]:
                        if isinstance(insn, ir.SetLocal):
                            # We've just initialized it.
                            block_state[env][var_name] = True
                            set_local_in_this_frame = True
                        else: # isinstance(insn, ir.GetLocal)
                            if not block_state[env][var_name]:
                                # Oops, accessing it uninitialized.
                                self._uninitialized_access(insn, var_name,
                                                           pred_at_fault(env, var_name))

                closures_to_check = []

                if (isinstance(insn, (ir.SetLocal, ir.SetAttr, ir.SetElem)) and
                        not set_local_in_this_frame):
                    # Closures may escape via these mechanisms and be invoked elsewhere.
                    if isinstance(insn.value(), ir.Closure):
                        closures_to_check.append(insn.value())

                if isinstance(insn, (ir.Call, ir.Invoke)):
                    # We can't always trace the flow of closures from point of
                    # definition to point of call; however, we know that, by transitiveness
                    # of this analysis, only closures defined in this function can contain
                    # uninitialized variables.
                    #
                    # Thus, enumerate the closures, and check all of them during any operation
                    # that may eventually result in the closure being called.
                    closures_to_check = closures

                for closure in closures_to_check:
                    env = closure.environment()
                    # Make sure this environment has any interesting variables.
                    if env in block_state:
                        for var_name in block_state[env]:
                            if not block_state[env][var_name] and not is_special_variable(var_name):
                                # A closure would capture this variable while it is not always
                                # initialized. Note that this check is transitive.
                                self._uninitialized_access(closure, var_name,
                                                           pred_at_fault(env, var_name))

            # Save the state.
            state[block] = block_state

            return block_state

        for block in func.basic_blocks:
            traverse(block)

    def _uninitialized_access(self, insn, var_name, pred_at_fault):
        if pred_at_fault is not None:
            visited = set()
            possible_preds = [pred_at_fault]

            uninitialized_loc = None
            while uninitialized_loc is None:
                possible_pred = possible_preds.pop(0)
                visited.add(possible_pred)

                for pred_insn in reversed(possible_pred.instructions):
                    if pred_insn.loc is not None:
                        uninitialized_loc = pred_insn.loc.begin()
                        break

                for block in possible_pred.predecessors():
                    if block not in visited:
                        possible_preds.append(block)

            assert uninitialized_loc is not None

            note = diagnostic.Diagnostic("note",
                "variable is not initialized when control flows from this point", {},
                uninitialized_loc)
        else:
            note = None

        if note is not None:
            notes = [note]
        else:
            notes = []

        if isinstance(insn, ir.Closure):
            diag = diagnostic.Diagnostic("error",
                "variable '{name}' can be captured in a closure uninitialized here",
                {"name": var_name},
                insn.loc, notes=notes)
        else:
            diag = diagnostic.Diagnostic("error",
                "variable '{name}' is not always initialized here",
                {"name": var_name},
                insn.loc, notes=notes)

        self.engine.process(diag)
