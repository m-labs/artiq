"""
Caches source files on import so that inspect.getsource returns the source code that
was imported (or at least with a small race window), not what is currently on the
filesystem at the time inspect.getsource is called.
This is a hack and it still has races, and it would be better if Python supported
this correctly, but it does not.
"""

import linecache
import tokenize
import logging


__all__ = ["install_hook", "add_module_to_cache"]


logger = logging.getLogger(__name__)


cache = dict()
linecache_getlines = None


def add_module_to_cache(module):
    if hasattr(module, "__file__"):
        fn = module.__file__
        try:
            with tokenize.open(fn) as fp:
                lines = fp.readlines()
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"
            cache[fn] = lines
        except:
            logger.warning("failed to add '%s' to cache", fn, exc_info=True)
        else:
            logger.debug("added '%s' to cache", fn)


def hook_getlines(filename, module_globals=None):
    if filename in cache:
        return cache[filename]
    else:
        return linecache_getlines(filename, module_globals)


def install_hook():
    global linecache_getlines

    linecache_getlines = linecache.getlines
    linecache.getlines = hook_getlines

    logger.debug("hook installed")
