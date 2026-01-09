#!/usr/bin/env python3

import os
from setuptools import setup
from setuptools.command.build_py import build_py as _build_py
from setuptools.command.sdist import sdist as _sdist


VERSION_FILE = """
def get_version():
    return "{version}"

def get_rev():
    return "{rev}"
"""


def get_version():
    return os.getenv("VERSIONEER_OVERRIDE", default="9.0+unknown.beta")

def get_rev():
    return os.getenv("VERSIONEER_REV", default="unknown")

def write_to_version_file(filename, version, rev):
    os.unlink(filename)
    with open(filename, "w") as f:
        f.write(VERSION_FILE.format(version=version, rev=rev))


class cmd_build_py(_build_py):
    def run(self):
        _build_py.run(self)
        target = os.path.join(self.build_lib, "artiq", "_version.py")
        print("UPDATING %s" % target)
        write_to_version_file(target, get_version(), get_rev())


class cmd_sdist(_sdist):
    def run(self):
        version = get_version()
        self._generated_version = version
        self._rev = get_rev()
        # unless we update this, the command will keep using the old
        # version
        self.distribution.metadata.version = version
        return _sdist.run(self)

    def make_release_tree(self, base_dir, files):
        _sdist.make_release_tree(self, base_dir, files)
        target_versionfile = os.path.join(base_dir, "artiq", "_version.py")
        print("UPDATING %s" % target_versionfile)
        write_to_version_file(target_versionfile,
                              self._generated_version,
                              self._rev)

setup(
    version=get_version(),
    cmdclass={
        "build_py": cmd_build_py,
        "sdist": cmd_sdist,
    },
)
