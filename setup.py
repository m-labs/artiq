#!/usr/bin/python
# -*- coding: utf8 -*-

from setuptools import setup, find_packages
from glob import glob

setup(
        name = "artiq",
        version = "0.0+dev",
        author = u"Sébastien Bourdeauducq & NIST Ion Storage Group",
        author_email = "sb@m-labs.hk",
        url = "http://github.com/m-labs/artiq/",
        description = "Experiment Control",
        long_description = open("README.rst").read(),
        license = "BSD",
        install_requires = [
            "numpy", "scipy", "sphinx", "numpydoc", "nose",
        ],
        extras_require = {},
        dependency_links = [],
        packages = find_packages(),
        namespace_packages = [],
        test_suite = "nose.collector",
        include_package_data = True,
        ext_modules=[],
        )
