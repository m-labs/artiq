#!/usr/bin/env python3

from setuptools import setup, find_packages
from glob import glob
import os


setup(
    name="artiq",
    version="0.0+dev",
    author="M-Labs / NIST Ion Storage Group",
    author_email="sb@m-labs.hk",
    url="http://m-labs.hk/artiq",
    description="A control system for trapped-ion experiments",
    long_description=open("README.rst").read(),
    license="BSD",
    install_requires=[
        "sphinx", "pyserial", "numpy", "scipy", "prettytable"
    ],
    extras_require={},
    dependency_links=[],
    packages=find_packages(),
    namespace_packages=[],
    test_suite="artiq.test",
    data_files=[
        (os.path.join("artiq", "gui"),
         [os.path.join("artiq", "gui", "icon.png")])],
    ext_modules=[],
    entry_points={
        "console_scripts": [
            "artiq_client=artiq.frontend.artiq_client:main",
            "artiq_ctlid=artiq.frontend.artiq_ctlid:main",
            "artiq_gui=artiq.frontend.artiq_gui:main",
            "artiq_master=artiq.frontend.artiq_master:main",
            "artiq_run=artiq.frontend.artiq_run:main",
            "lda_client=artiq.frontend.lda_client:main",
            "lda_controller=artiq.frontend.lda_controller:main",
            "pdq2_client=artiq.frontend.pdq2_client:main",
            "pdq2_controller=artiq.frontend.pdq2_controller:main",
        ],
    }
)
