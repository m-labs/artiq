import asyncio
import importlib.util
import importlib.machinery
import inspect
import logging
import os
import pathlib
import string
import sys

import numpy as np

from sipyco import pyon

from artiq import __version__ as artiq_version
from artiq.appdirs import user_config_dir
from artiq.language.environment import is_public_experiment
from artiq.language import units


__all__ = ["parse_arguments",
           "parse_devarg_override", "unparse_devarg_override",
           "elide", "scale_from_metadata",
           "short_format", "file_import",
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


def parse_devarg_override(devarg_override):
    devarg_override_dict = {}
    for item in devarg_override.split():
        device, _, override = item.partition(":")
        if not override:
            raise ValueError
        if device not in devarg_override_dict:
            devarg_override_dict[device] = {}
        argument, _, value = override.partition("=")
        if not value:
            raise ValueError
        devarg_override_dict[device][argument] = pyon.decode(value)
    return devarg_override_dict


def unparse_devarg_override(devarg_override):
    devarg_override_strs = [
        "{}:{}={}".format(device, argument, pyon.encode(value))
        for device, overrides in devarg_override.items()
        for argument, value in overrides.items()]
    return " ".join(devarg_override_strs)


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

def scale_from_metadata(metadata):
    unit = metadata.get("unit", "")
    default_scale = getattr(units, unit, 1)
    return metadata.get("scale", default_scale)  

def short_format(v, metadata={}):
    m = metadata
    unit = m.get("unit", "")
    scale = scale_from_metadata(m)
    precision = m.get("precision", None)
    if v is None:
        return "None"
    t = type(v)
    if np.issubdtype(t, np.number):
        v_t = np.divide(v, scale)
        v_str = np.format_float_positional(v_t, 
                                           precision=precision,
                                           trim='-',
                                           unique=True)
        v_str += " " + unit if unit else ""
        return v_str
    elif np.issubdtype(t, np.bool_):
       return str(v)
    elif np.issubdtype(t, np.str_):
        return "\"" + elide(v, 50) + "\""
    elif t is np.ndarray:
        v_t = np.divide(v, scale)
        v_str = np.array2string(v_t,
                                max_line_width=1000,
                                precision=precision,
                                suppress_small=True,
                                separator=', ',
                                threshold=4,
                                edgeitems=2,
                                floatmode='maxprec')
        v_str += " " + unit if unit else ""
        return v_str
    elif isinstance(v, (dict, list)):
        r = t.__name__ + " ({})".format(len(v))
        return r


def file_import(filename, prefix="file_import_"):
    filename = pathlib.Path(filename)
    modname = prefix + filename.stem

    path = str(filename.resolve().parent)
    sys.path.insert(0, path)

    try:
        spec = importlib.util.spec_from_loader(
            modname,
            importlib.machinery.SourceFileLoader(modname, str(filename)),
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(path)

    return module


def get_experiment(module, class_name=None):
    if class_name:
        obj = module
        for name in class_name.split('.'):
            obj = getattr(obj, name)
        return obj

    exps = inspect.getmembers(module, is_public_experiment)

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
