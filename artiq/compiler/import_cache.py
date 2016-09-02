import sys
import builtins
import linecache
import tokenize
import logging
import importlib.machinery as im

from artiq.experiment import kernel, portable


__all__ = ["install_hook"]


logger = logging.getLogger(__name__)


cache = dict()
im_exec_module = None
linecache_getlines = None


def hook_exec_module(self, module):
    im_exec_module(self, module)
    if (hasattr(module, "__file__")
            # Heuristic to determine if the module may contain ARTIQ kernels.
            # This breaks if kernel is not imported the usual way.
            and ((getattr(module, "kernel", None) is kernel)
                 or (getattr(module, "portable", None) is portable))):
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
    global im_exec_module, linecache_getlines

    im_exec_module = im.SourceFileLoader.exec_module
    im.SourceFileLoader.exec_module = hook_exec_module

    linecache_getlines = linecache.getlines
    linecache.getlines = hook_getlines

    logger.debug("hook installed")
