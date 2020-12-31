__all__ = []

_prefixes_str = "pnum_kMG"
_smallest_prefix_exp = -12


def _register_unit(unit, prefixes):
    exponent = _smallest_prefix_exp
    for prefix in _prefixes_str:
        if prefix in prefixes:
            full_name = prefix + unit if prefix != "_" else unit
            globals()[full_name] = 10.**exponent
            __all__.append(full_name)
        exponent += 3


_register_unit("s", "pnum_")
_register_unit("Hz", "m_kMG")
_register_unit("dB", "_")
_register_unit("V", "um_k")
_register_unit("A", "um_")
_register_unit("W", "um_")
