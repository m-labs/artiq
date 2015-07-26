#!/usr/bin/env python3

from setuptools import setup, find_packages, Command
import sys
import os

if sys.version_info[:3] < (3, 4, 3):
    raise Exception("You need at least Python 3.4.3 to run ARTIQ")

class PushDocCommand(Command):
    description = "uploads the documentation to m-labs.hk"
    user_options = []
    def initialize_options(self):
        pass
    def finalize_options(self):
        pass
    def run(self):
        os.system("rsync -avz doc/manual/_build/html/ shell.serverraum.org:~/web/m-labs.hk/artiq/manual")

requirements = [
    "sphinx", "sphinx-argparse", "pyserial", "numpy", "scipy",
    "python-dateutil", "prettytable", "h5py", "pydaqmx", "pyelftools",
    "quamash", "pyqtgraph"
]

scripts = [
    "artiq_client=artiq.frontend.artiq_client:main",
    "artiq_compile=artiq.frontend.artiq_compile:main",
    "artiq_coreconfig=artiq.frontend.artiq_coreconfig:main",
    "artiq_ctlmgr=artiq.frontend.artiq_ctlmgr:main",
    "artiq_gui=artiq.frontend.artiq_gui:main",
    "artiq_master=artiq.frontend.artiq_master:main",
    "artiq_mkfs=artiq.frontend.artiq_mkfs:main",
    "artiq_rpctool=artiq.frontend.artiq_rpctool:main",
    "artiq_run=artiq.frontend.artiq_run:main",
    "lda_controller=artiq.frontend.lda_controller:main",
    "novatech409b_controller=artiq.frontend.novatech409b_controller:main",
    "pdq2_client=artiq.frontend.pdq2_client:main",
    "pdq2_controller=artiq.frontend.pdq2_controller:main",
    "pxi6733_controller=artiq.frontend.pxi6733_controller:main",
    "thorlabs_tcube_controller=artiq.frontend.thorlabs_tcube_controller:main",
]

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
        "git+https://github.com/pyqtgraph/pyqtgraph.git@a6d5e28#egg=pyqtgraph"
    ],
    packages=find_packages(),
    namespace_packages=[],
    test_suite="artiq.test",
    package_data={"artiq": [os.path.join("gui", "icon.png")]},
    ext_modules=[],
    entry_points={
        "console_scripts": scripts,
    },
    cmdclass={"push_doc":PushDocCommand}
)
