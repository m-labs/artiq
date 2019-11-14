# This script installs ARTIQ using the conda packages built by the new Nix/Hydra system.
# It needs to be run in the root (base) conda environment with "python install-with-conda.py"
# It supports Linux and Windows, but Linux users should consider using the higher-quality
# Nix package manager instead of Conda.

# EDIT THIS:
# The name of the conda environment to create
CONDA_ENV_NAME = "artiq"
# The conda packages to download and install.
CONDA_PACKAGES = [
    "artiq",
    "artiq-comtools",
    # Only install board packages if you plan to reflash the board.
    # The two lines below are just examples and probably not what you want.
    # Select the packages that correspond to your board, or remove them
    # if you do not intend to reflash the board.
    "artiq-board-kc705-nist_clock",
    "artiq-board-kasli-wipm"
]
# Set to False if you have already set up conda channels
ADD_CHANNELS = True

# PROXY: If you are behind a web proxy, configure it in your .condarc (as per
# the conda manual).

# You should not need to modify the rest of the script below.

import os

def run(command):
    r = os.system(command)
    if r != 0:
        raise SystemExit("command '{}' returned non-zero exit status: {}".format(command, r))

if ADD_CHANNELS:
    run("conda config --prepend channels m-labs")
    run("conda config --prepend channels https://conda.m-labs.hk/artiq-beta")
    run("conda config --append channels conda-forge")

# Creating the environment first with python 3.5 hits fewer bugs in conda's broken dependency solver.
run("conda create -y -n {CONDA_ENV_NAME} python=3.5".format(CONDA_ENV_NAME=CONDA_ENV_NAME))
for package in CONDA_PACKAGES:
    # Do not activate the environment yet - otherwise "conda install" may not find the SSL module anymore on Windows.
    # Installing into the environment from the outside works around this conda bug.
    run("conda install -y -n {CONDA_ENV_NAME} -c https://conda.m-labs.hk/artiq-beta {package}"
        .format(CONDA_ENV_NAME=CONDA_ENV_NAME, package=package))
