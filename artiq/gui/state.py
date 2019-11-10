import asyncio
from collections import OrderedDict
import logging

from sipyco.asyncio_tools import TaskObject
from sipyco import pyon


logger = logging.getLogger(__name__)


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
            logger.info("State database '%s' not found, using defaults",
                        self.filename)
            return
        # The state of one object may depend on the state of another,
        # e.g. the display state may create docks that are referenced in
        # the area state.
        # To help address this problem, state is restored in the opposite
        # order as the stateful objects are registered.
        for name, obj in reversed(list(self.stateful_objects.items())):
            logger.debug("Restoring state of object '%s'", name)
            state = data.get(name, None)
            if state is not None:
                try:
                    _restore_state(obj, state)
                except:
                    logger.warning("Failed to restore state for object '%s'",
                                   name, exc_info=True)

    def save(self):
        data = dict()
        for k, v in self.stateful_objects.items():
            try:
                data[k] = _save_state(v)
            except:
                logger.warning("Failed to save state for object '%s'", k,
                               exc_info=True)
        pyon.store_file(self.filename, data)

    async def _do(self):
        try:
            try:
                while True:
                    await asyncio.sleep(self.autosave_period)
                    self.save()
            finally:
                self.save()
        except asyncio.CancelledError:
            pass
        except:
            logger.error("Uncaught exception attempting to save state",
                         exc_info=True)
