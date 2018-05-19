"""
:class:`LocalDemoter` is a constant propagation transform:
it replaces reads of any local variable with only one write
in a function without closures with the value that was written.

:class:`LocalAccessValidator` must be run before this transform
to ensure that the transformation it performs is sound.
"""

from collections import defaultdict
from .. import ir

class LocalDemoter:
    def process(self, functions):
        for func in functions:
            self.process_function(func)

    def process_function(self, func):
        env_safe = {}
        env_gets = defaultdict(lambda: set())
        env_sets = defaultdict(lambda: set())

        for insn in func.instructions():
            if isinstance(insn, (ir.GetLocal, ir.SetLocal)):
                if "$" in insn.var_name:
                    continue

                env = insn.environment()

                if env not in env_safe:
                    for use in env.uses:
                        if not isinstance(use, (ir.GetLocal, ir.SetLocal)):
                            env_safe[env] = False
                            break
                    else:
                        env_safe[env] = True

                if not env_safe[env]:
                    continue

                if isinstance(insn, ir.SetLocal):
                    env_sets[(env, insn.var_name)].add(insn)
                else:
                    env_gets[(env, insn.var_name)].add(insn)

        for (env, var_name) in env_sets:
            if len(env_sets[(env, var_name)]) == 1:
                set_insn = next(iter(env_sets[(env, var_name)]))
                for get_insn in env_gets[(env, var_name)]:
                    get_insn.replace_all_uses_with(set_insn.value())
                    get_insn.erase()
