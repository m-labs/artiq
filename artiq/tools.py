import asyncio
import importlib.machinery
import logging
import os
import string
import sys

import numpy as np

from sipyco import pyon

from artiq import __version__ as artiq_version
from artiq.appdirs import user_config_dir
from artiq.language.environment import is_experiment


__all__ = ["parse_arguments", "elide", "short_format", "file_import",
           "get_experiment",
           "exc_to_warning", "asyncio_wait_or_cancel",
           "get_windows_drives", "get_user_config_dir"]


logger = logging.getLogger(__name__)


def parse_arguments(arguments):
    d = {}
    for argument in arguments:
        name, eq, value = argument.partition("=")
        d[name] = pyon.decode(value)
    return d


def elide(s, maxlen):
    elided = False
    if len(s) > maxlen:
        s = s[:maxlen]
        elided = True
    try:
        idx = s.index("\n")
    except ValueError:
        pass
    else:
        s = s[:idx]
        elided = True
    if elided:
        maxlen -= 3
        if len(s) > maxlen:
            s = s[:maxlen]
        s += "..."
    return s


def short_format(v):
    if v is None:
        return "None"
    t = type(v)
    if np.issubdtype(t, np.number) or np.issubdtype(t, np.bool_):
        return str(v)
    elif np.issubdtype(t, np.unicode_):
        return "\"" + elide(v, 50) + "\""
    else:
        r = t.__name__
        if t is list or t is dict or t is set:
            r += " ({})".format(len(v))
        if t is np.ndarray:
            r += " " + str(np.shape(v))
        return r


def file_import(filename, prefix="file_import_"):
    modname = filename
    i = modname.rfind("/")
    if i > 0:
        modname = modname[i+1:]
    i = modname.find(".")
    if i > 0:
        modname = modname[:i]
    modname = prefix + modname

    path = os.path.dirname(os.path.realpath(filename))
    sys.path.insert(0, path)
    try:
        loader = importlib.machinery.SourceFileLoader(modname, filename)
        module = loader.load_module()
    finally:
        sys.path.remove(path)

    return module


def get_experiment(module, class_name=None):
    if class_name:
        return getattr(module, class_name)

    exps = [(k, v) for k, v in module.__dict__.items()
            if k[0] != "_" and is_experiment(v)]
    if not exps:
        raise ValueError("No experiments in module")
    if len(exps) > 1:
        raise ValueError("More than one experiment found in module")
    return exps[0][1]


async def exc_to_warning(coro):
    try:
        await coro
    except:
        logger.warning("asyncio coroutine terminated with exception",
                       exc_info=True)


async def asyncio_wait_or_cancel(fs, **kwargs):
    fs = [asyncio.ensure_future(f) for f in fs]
    try:
        d, p = await asyncio.wait(fs, **kwargs)
    except:
        for f in fs:
            f.cancel()
        raise
    for f in p:
        f.cancel()
        await asyncio.wait([f])
    return fs


def get_windows_drives():
    from ctypes import windll

    drives = []
    bitmask = windll.kernel32.GetLogicalDrives()
    for letter in string.ascii_uppercase:
        if bitmask & 1:
            drives.append(letter)
        bitmask >>= 1
    return drives


def get_user_config_dir():
    major = artiq_version.split(".")[0]
    dir = user_config_dir("artiq", "m-labs", major)
    os.makedirs(dir, exist_ok=True)
    return dir
