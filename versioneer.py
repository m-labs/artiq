import os
import sys

VERSION_FILE = """
def get_version():
    return "{version}"
"""

def get_version():
    override = os.getenv("VERSIONEER_OVERRIDE")
    if override:
      return override
    srcroot = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(srcroot, "MAJOR_VERSION"), "r") as f:
        version = f.read().strip()
    version += ".unknown"
    if os.path.exists(os.path.join(srcroot, "BETA")):
        version += ".beta"
    return version

def write_to_version_file(filename, version):
    os.unlink(filename)
    with open(filename, "w") as f:
        f.write(VERSION_FILE.format(version=version))


def get_cmdclass():
    cmds = {}

    # we override different "build_py" commands for both environments
    if "setuptools" in sys.modules:
        from setuptools.command.build_py import build_py as _build_py
    else:
        from distutils.command.build_py import build_py as _build_py

    class cmd_build_py(_build_py):
        def run(self):
            version = get_version()
            _build_py.run(self)
            target_versionfile = os.path.join(self.build_lib,
                                              "artiq", "_version.py")
            print("UPDATING %s" % target_versionfile)
            write_to_version_file(target_versionfile, version)
    cmds["build_py"] = cmd_build_py


    # we override different "sdist" commands for both environments
    if "setuptools" in sys.modules:
        from setuptools.command.sdist import sdist as _sdist
    else:
        from distutils.command.sdist import sdist as _sdist

    class cmd_sdist(_sdist):
        def run(self):
            version = get_version()
            self._versioneer_generated_version = version
            # unless we update this, the command will keep using the old
            # version
            self.distribution.metadata.version = version
            return _sdist.run(self)

        def make_release_tree(self, base_dir, files):
            _sdist.make_release_tree(self, base_dir, files)
            target_versionfile = os.path.join(base_dir, "artiq", "_version.py")
            print("UPDATING %s" % target_versionfile)
            write_to_version_file(target_versionfile,
                                  self._versioneer_generated_version)
    cmds["sdist"] = cmd_sdist

    return cmds
