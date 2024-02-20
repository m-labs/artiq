from numpy import int32

from artiq.language.core import nac3, extern, kernel, KernelInvariant
from artiq.coredevice.core import Core


@extern
def cache_get(key: str) -> list[int32]:
    raise NotImplementedError("syscall not simulated")

@extern
def cache_put(key: str, value: list[int32]):
    raise NotImplementedError("syscall not simulated")


@nac3
class CoreCache:
    """Core device cache access"""

    core: KernelInvariant[Core]

    def __init__(self, dmgr, core_device="core"):
        self.core = dmgr.get(core_device)

    # NAC3TODO
    # @kernel
    # def get(self, key: str) -> list[int32]:
    #     """Extract a value from the core device cache.
    #     After a value is extracted, it cannot be replaced with another value using
    #     :meth:`put` until all kernel functions finish executing; attempting
    #     to replace it will result in a :class:`artiq.coredevice.exceptions.CacheError`.
    #
    #     If the cache does not contain any value associated with ``key``, an empty list
    #     is returned.
    #
    #     The value is not copied, so mutating it will change what's stored in the cache.
    #
    #     :param str key: cache key
    #     :return: a list of 32-bit integers
    #     """
    #     return cache_get(key)

    @kernel
    def put(self, key: str, value: list[int32]):
        """Put a value into the core device cache. The value will persist until reboot.

        To remove a value from the cache, call :meth:`put` with an empty list.

        :param str key: cache key
        :param list value: a list of 32-bit integers
        """
        cache_put(key, value)
