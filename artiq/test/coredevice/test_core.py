import unittest
import logging
import numpy as np

from artiq.experiment import kernel

import artiq.coredevice.core


class _Core(artiq.coredevice.core.Core):
    def __init__(self, *args, **kwargs):
        super(_Core, self).__init__(*args, **kwargs)
        self.dmgr['core'] = self
        self.kernel_size = 0

    def compile(self, *args, **kwargs):
        embedding_map, kernel_library, symbolizer, demangler = \
            super(_Core, self).compile(*args, **kwargs)
        self.kernel_size = len(kernel_library)
        return embedding_map, kernel_library, symbolizer, demangler


class CoreTestCase(unittest.TestCase):

    def test_string_to_bytes(self):
        data = [
            ('0b', 0),
            ('15b', 15),
            ('1kb', 1 * 1000 ** 1),
            ('1 kb', 1 * 1000 ** 1),
            ('   1   kb  ', 1 * 1000 ** 1),
            ('1KB', 1 * 1000 ** 1),
            ('1kB', 1 * 1000 ** 1),
            ('2kb', 2 * 1000 ** 1),
            ('323 kb', 323 * 1000 ** 1),
            ('3 mb', 3 * 1000 ** 2),
            ('77gb', 77 * 1000 ** 3),
            ('7kib', 7 * 1024 ** 1),
            ('7mib', 7 * 1024 ** 2),
            ('7gib', 7 * 1024 ** 3),
            ('7 gib', 7 * 1024 ** 3),
            ('7 GiB', 7 * 1024 ** 3),
        ]

        for s, r in data:
            self.assertEqual(artiq.coredevice.core._str_to_bytes(s), r)


class CoreCompilingTestCase(unittest.TestCase):

    def _set_core(self, **kwargs):
        kwargs.setdefault('host', None)
        kwargs.setdefault('ref_period', 1e-9)
        self._update_kernel_invariants('core', clear=True)
        self.core = _Core({}, **kwargs)

    def _update_kernel_invariants(self, *args: str, clear: bool = False) -> None:
        kernel_invariants = set() if clear else getattr(self, 'kernel_invariants', set())
        self.kernel_invariants = kernel_invariants | set(args)

    def test_max_kernel_size(self):
        # Calculate reference size
        self._set_core()
        self.data = np.empty(1, dtype=np.int32)
        self._update_kernel_invariants('data')
        self._kernel()
        ref_size = self.core.kernel_size - 4  # Minus the one element used for testing the size

        sizes = [100, 256, 300, 512]

        for size in sizes:
            self._set_core(max_kernel_size='{}b'.format(size * 4 + ref_size))
            self.data = np.empty(size, dtype=np.int32)
            self._update_kernel_invariants('data')
            self._kernel()  # Fits exactly, does not raise
            with self.assertRaises(artiq.coredevice.core.KernelSizeException,
                                   msg='Kernel size exception did not raise'):
                self.data = np.empty(size + 1, dtype=np.int32)
                self._kernel()  # One byte too big, should raise

    def test_log(self):
        self._set_core()
        self.data = np.empty(1, dtype=np.int32)
        self._update_kernel_invariants('data')
        with self.assertLogs(artiq.coredevice.core.logger, logging.DEBUG):
            self._kernel()

    @kernel
    def _kernel(self):
        # Address `data` to get it compiled
        for d in self.data:
            print(d)
