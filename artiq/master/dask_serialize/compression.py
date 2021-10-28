"""
Record known compressors

Includes utilities for determining whether or not to compress
"""
from __future__ import annotations

import logging
import random
from collections.abc import Callable
from contextlib import suppress
from functools import partial
from typing import TYPE_CHECKING


blosc = False


def ensure_bytes(s):
    """Attempt to turn `s` into bytes.

    Parameters
    ----------
    s : Any
        The object to be converted. Will correctly handled

        * str
        * bytes
        * objects implementing the buffer protocol (memoryview, ndarray, etc.)

    Returns
    -------
    b : bytes

    Raises
    ------
    TypeError
        When `s` cannot be converted

    Examples
    --------
    >>> ensure_bytes('123')
    b'123'
    >>> ensure_bytes(b'123')
    b'123'
    """
    if isinstance(s, bytes):
        return s
    elif hasattr(s, "encode"):
        return s.encode()
    else:
        try:
            return bytes(s)
        except Exception as e:
            raise TypeError(
                "Object %s is neither a bytes object nor has an encode method" % s
            ) from e


identity = lambda x: x

if TYPE_CHECKING:
    from typing_extensions import Literal

compressions: dict[
    str | None | Literal[False],
    dict[Literal["compress", "decompress"], Callable[[bytes], bytes]],
] = {None: {"compress": identity, "decompress": identity}}

compressions[False] = compressions[None]  # alias


default_compression = None


logger = logging.getLogger(__name__)


with suppress(ImportError):
    import zlib

    compressions["zlib"] = {"compress": zlib.compress, "decompress": zlib.decompress}


def get_default_compression():
    default = "auto"
    if default != "auto":
        if default in compressions:
            return default
        else:
            raise ValueError(
                "Default compression '%s' not found.\n"
                "Choices include auto, %s"
                % (default, ", ".join(sorted(map(str, compressions))))
            )
    else:
        return default_compression


get_default_compression()


def byte_sample(b, size, n):
    """Sample a bytestring from many locations

    Parameters
    ----------
    b : bytes or memoryview
    size : int
        size of each sample to collect
    n : int
        number of samples to collect
    """
    starts = [random.randint(0, len(b) - size) for j in range(n)]
    ends = []
    for i, start in enumerate(starts[:-1]):
        ends.append(min(start + size, starts[i + 1]))
    ends.append(starts[-1] + size)

    parts = [b[start:end] for start, end in zip(starts, ends)]
    return b"".join(map(ensure_bytes, parts))


def maybe_compress(
    payload,
    min_size=1e4,
    sample_size=1e4,
    nsamples=5,
    compression="auto",
):
    """
    Maybe compress payload

    1.  We don't compress small messages
    2.  We sample the payload in a few spots, compress that, and if it doesn't
        do any good we return the original
    3.  We then compress the full original, it it doesn't compress well then we
        return the original
    4.  We return the compressed result
    """
    if compression == "auto":
        compression = default_compression

    if not compression:
        return None, payload
    if len(payload) < min_size:
        return None, payload
    if len(payload) > 2 ** 31:  # Too large, compression libraries often fail
        return None, payload

    min_size = int(min_size)
    sample_size = int(sample_size)

    compress = compressions[compression]["compress"]

    # Compress a sample, return original if not very compressed
    sample = byte_sample(payload, sample_size, nsamples)
    if len(compress(sample)) > 0.9 * len(sample):  # sample not very compressible
        return None, payload

    if type(payload) is memoryview:
        nbytes = payload.itemsize * len(payload)
    else:
        nbytes = len(payload)

    if default_compression and blosc and type(payload) is memoryview:
        # Blosc does itemsize-aware shuffling, resulting in better compression
        compressed = blosc.compress(
            payload, typesize=payload.itemsize, cname="lz4", clevel=5
        )
        compression = "blosc"
    else:
        compressed = compress(ensure_bytes(payload))

    if len(compressed) > 0.9 * nbytes:  # full data not very compressible
        return None, payload
    else:
        return compression, compressed


def decompress(header, frames):
    """Decompress frames according to information in the header"""
    return [
        compressions[c]["decompress"](frame)
        for c, frame in zip(header["compression"], frames)
    ]
