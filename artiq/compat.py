import json
import warnings

from sipyco import pyon, pyon_v1


def pyon_decode(s):
    try:
        return pyon.decode(s)
    except json.JSONDecodeError:
        try:
            return pyon_v1.decode(s)
        except:
            raise


def pyon_load_file(filename):
    try:
        return pyon.load_file(filename)
    except json.JSONDecodeError:
        try:
            return pyon_v1.load_file(filename)
        except:
            raise
