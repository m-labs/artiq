import asyncio
from collections import OrderedDict

from artiq.tools import TaskObject
from artiq.protocols import pyon


# support Qt CamelCase naming scheme for save/restore state
def _save_state(obj):
    method = getattr(obj, "save_state", None)
    if method is None:
        method = obj.saveState
    return method()


def _restore_state(obj, state):
    method = getattr(obj, "restore_state", None)
    if method is None:
        method = obj.restoreState
    method(state)


class StateManager(TaskObject):
    def __init__(self, filename, autosave_period=30):
        self.filename = filename
        self.autosave_period = autosave_period
        self.stateful_objects = OrderedDict()

    def register(self, obj, name=None):
        if name is None:
            name = obj.__class__.__name__
        if name in self.stateful_objects:
            raise RuntimeError("Name '{}' already exists in state"
                               .format(name))
        self.stateful_objects[name] = obj

    def load(self):
        try:
            data = pyon.load_file(self.filename)
        except FileNotFoundError:
            return
        # The state of one object may depend on the state of another,
        # e.g. the display state may create docks that are referenced in
        # the area state.
        # To help address this problem, state is restored in the opposite
        # order as the stateful objects are registered.
        for name, obj in reversed(list(self.stateful_objects.items())):
            state = data.get(name, None)
            if state is not None:
                _restore_state(obj, state)

    def save(self):
        data = {k: _save_state(v) for k, v in self.stateful_objects.items()}
        pyon.store_file(self.filename, data)

    @asyncio.coroutine
    def _do(self):
        try:
            while True:
                yield from asyncio.sleep(self.autosave_period)
                self.save()
        finally:
            self.save()
