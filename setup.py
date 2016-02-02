#!/usr/bin/env python3.5

from setuptools import setup, find_packages
import sys
import os

import versioneer


if sys.version_info[:3] < (3, 5, 1):
    raise Exception("You need Python 3.5.1+")


requirements = [
    "sphinx", "sphinx-argparse", "pyserial", "numpy", "scipy",
    "python-dateutil", "prettytable", "h5py", "pydaqmx",
    "quamash", "pyqtgraph", "pygit2", "aiohttp",
    "llvmlite_artiq", "pythonparser", "python-Levenshtein",
    "lit", "OutputCheck",
]

scripts = [
    "artiq_client=artiq.frontend.artiq_client:main",
    "artiq_compile=artiq.frontend.artiq_compile:main",
    "artiq_coreanalyzer=artiq.frontend.artiq_coreanalyzer:main",
    "artiq_coreconfig=artiq.frontend.artiq_coreconfig:main",
    "artiq_corelog=artiq.frontend.artiq_corelog:main",
    "artiq_ctlmgr=artiq.frontend.artiq_ctlmgr:main",
    "artiq_gui=artiq.frontend.artiq_gui:main",
    "artiq_influxdb=artiq.frontend.artiq_influxdb:main",
    "artiq_master=artiq.frontend.artiq_master:main",
    "artiq_mkfs=artiq.frontend.artiq_mkfs:main",
    "artiq_rpctool=artiq.frontend.artiq_rpctool:main",
    "artiq_run=artiq.frontend.artiq_run:main",
    "artiq_flash=artiq.frontend.artiq_flash:main",
    "lda_controller=artiq.frontend.lda_controller:main",
    "novatech409b_controller=artiq.frontend.novatech409b_controller:main",
    "pdq2_client=artiq.frontend.pdq2_client:main",
    "pdq2_controller=artiq.frontend.pdq2_controller:main",
    "pxi6733_controller=artiq.frontend.pxi6733_controller:main",
    "thorlabs_tcube_controller=artiq.frontend.thorlabs_tcube_controller:main",
]

setup(
    name="artiq",
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    author="M-Labs / NIST Ion Storage Group",
    author_email="sb@m-labs.hk",
    url="http://m-labs.hk/artiq",
    description="A control system for trapped-ion experiments",
    long_description=open("README.rst").read(),
    license="GPL",
    install_requires=requirements,
    extras_require={},
    dependency_links=[
        "git+https://github.com/m-labs/pyqtgraph.git@develop#egg=pyqtgraph",
        "git+https://github.com/m-labs/llvmlite.git@artiq#egg=llvmlite_artiq"
    ],
    packages=find_packages(),
    namespace_packages=[],
    test_suite="artiq.test",
    include_package_data=True,
    ext_modules=[],
    entry_points={
        "console_scripts": scripts,
    }
)
