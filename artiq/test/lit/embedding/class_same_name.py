# RUN: %python -m artiq.compiler.testbench.embedding %s

from artiq.language.core import *


class InnerA:
    def __init__(self, val):
        self.val = val

    @kernel
    def run_once(self):
        return self.val


class InnerB:
    def __init__(self, val):
        self.val = val

    @kernel
    def run_once(self):
        return self.val


def make_runner(InnerCls, val):
    class Runner:
        def __init__(self):
            self.inner = InnerCls(val)

        @kernel
        def run_once(self):
            return self.inner.run_once()

    return Runner()


class Parent:
    def __init__(self):
        self.a = make_runner(InnerA, 1)
        self.b = make_runner(InnerB, 42.0)

    @kernel
    def run_once(self):
        return self.a.run_once() + self.b.run_once()


parent = Parent()


@kernel
def entrypoint():
    parent.run_once()
