#!/usr/bin/env python3
# -*- coding: utf8 -*-

from setuptools import setup, find_packages
from glob import glob
import os


setup(
    name = "artiq",
    version = "0.0+dev",
    author = "M-Labs / NIST Ion Storage Group",
    author_email = "sb@m-labs.hk",
    url = "http://m-labs.hk/artiq",
    description = "A control system for trapped-ion experiments",
    long_description = open("README.rst").read(),
    license = "BSD",
    install_requires = [
        "sphinx", "numpy", "scipy"
    ],
    extras_require = {},
    dependency_links = [],
    packages = find_packages(),
    namespace_packages = [],
    test_suite = "artiq.test",
    include_package_data = True,
    ext_modules=[],
    scripts=glob(os.path.join("frontend", "*.py"))
)
