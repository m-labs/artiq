#!/usr/bin/env python3

from setuptools import setup, find_packages
import os


requirements = [
                "sphinx", "sphinx-argparse", "pyserial", "numpy", "scipy",
                "python-dateutil", "prettytable", "h5py"
               ]
if os.name != 'nt':
    requirements += ["pygobject", "gbulb", "cairoplot"]


setup(
    name="artiq",
    version="0.0+dev",
    author="M-Labs / NIST Ion Storage Group",
    author_email="sb@m-labs.hk",
    url="http://m-labs.hk/artiq",
    description="A control system for trapped-ion experiments",
    long_description=open("README.rst").read(),
    license="BSD",
    install_requires=requirements,
    extras_require={},
    dependency_links=[
        "git+https://github.com/m-labs/gbulb.git#egg=gbulb",
        "git+https://github.com/m-labs/cairoplot3.git#egg=cairoplot"
    ],
    packages=find_packages(),
    namespace_packages=[],
    test_suite="artiq.test",
    package_data={"artiq": [os.path.join("gui", "icon.png")]},
    ext_modules=[],
    entry_points={
        "console_scripts": [
            "artiq_client=artiq.frontend.artiq_client:main",
            "artiq_ctlid=artiq.frontend.artiq_ctlid:main",
            "artiq_ctlmgr=artiq.frontend.artiq_ctlmgr:main",
            "artiq_gui=artiq.frontend.artiq_gui:main",
            "artiq_master=artiq.frontend.artiq_master:main",
            "artiq_run=artiq.frontend.artiq_run:main",
            "lda_client=artiq.frontend.lda_client:main",
            "lda_controller=artiq.frontend.lda_controller:main",
            "pdq2_client=artiq.frontend.pdq2_client:main",
            "pdq2_controller=artiq.frontend.pdq2_controller:main",
            "example_artiq_device_client=artiq.frontend.example_artiq_device_client:main",
            "example_artiq_device_controller=example_artiq_device_controller:main"
        ],
    }
)
