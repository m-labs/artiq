import json
import warnings

from sipyco import pyon


def pyon_decode_compat(s):
    try:
        return pyon.decode(s)
    except json.JSONDecodeError as e:
        try:
            o = pyon.decode_v1(s)
            warnings.warn("Decoded as PYON v1")
            return o
        except:
            raise e


def pyon_load_file_compat(filename):
    try:
        return pyon.load_file(filename)
    except json.JSONDecodeError as e:
        try:
            with open(filename, "r", encoding="utf-8") as f:
                o = pyon.decode_v1(f.read())
                warnings.warn(f"Loaded `{filename}` as PYON v1")
                return o
        except:
            raise e
