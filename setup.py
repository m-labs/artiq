#!/usr/bin/env python3

from setuptools import setup, find_packages
import sys

import versioneer


if sys.version_info[:3] < (3, 5, 3):
    raise Exception("You need Python 3.5.3+")


# Depends on PyQt5, but setuptools cannot check for it.
requirements = [
    "numpy", "scipy",
    "python-dateutil", "prettytable", "h5py",
    "quamash", "pyqtgraph", "pygit2",
    "llvmlite_artiq", "pythonparser", "python-Levenshtein",
]

console_scripts = [
    "artiq_client = artiq.frontend.artiq_client:main",
    "artiq_compile = artiq.frontend.artiq_compile:main",
    "artiq_coreanalyzer = artiq.frontend.artiq_coreanalyzer:main",
    "artiq_coremgmt = artiq.frontend.artiq_coremgmt:main",
    "artiq_ddb_template = artiq.frontend.artiq_ddb_template:main",
    "artiq_netboot = artiq.frontend.artiq_netboot:main",
    "artiq_master = artiq.frontend.artiq_master:main",
    "artiq_mkfs = artiq.frontend.artiq_mkfs:main",
    "artiq_rtiomon = artiq.frontend.artiq_rtiomon:main",
    "artiq_sinara_tester = artiq.frontend.artiq_sinara_tester:main",
    "artiq_session = artiq.frontend.artiq_session:main",
    "artiq_route = artiq.frontend.artiq_route:main",
    "artiq_run = artiq.frontend.artiq_run:main",
    "artiq_flash = artiq.frontend.artiq_flash:main",
    "aqctl_corelog = artiq.frontend.aqctl_corelog:main",
]

gui_scripts = [
    "artiq_browser = artiq.frontend.artiq_browser:main",
    "artiq_dashboard = artiq.frontend.artiq_dashboard:main",
]

setup(
    name="artiq",
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    author="M-Labs",
    author_email="artiq@lists.m-labs.hk",
    url="https://m-labs.hk/artiq",
    description="Advanced Real-Time Infrastructure for Quantum physics",
    long_description=open("README.rst", encoding="utf-8").read(),
    license="LGPLv3+",
    classifiers="""\
Development Status :: 5 - Production/Stable
Environment :: Console
Environment :: X11 Applications :: Qt
Intended Audience :: Science/Research
License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)
Operating System :: Microsoft :: Windows
Operating System :: POSIX :: Linux
Programming Language :: Python :: 3.5
Topic :: Scientific/Engineering :: Physics
Topic :: System :: Hardware
""".splitlines(),
    install_requires=requirements,
    extras_require={},
    dependency_links=[
        "git+https://github.com/m-labs/pyqtgraph.git@develop#egg=pyqtgraph",
        "git+https://github.com/m-labs/llvmlite.git@artiq#egg=llvmlite_artiq"
    ],
    packages=find_packages(),
    namespace_packages=[],
    include_package_data=True,
    ext_modules=[],
    entry_points={
        "console_scripts": console_scripts,
        "gui_scripts": gui_scripts,
    }
)
