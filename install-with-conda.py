# This script installs ARTIQ using the conda packages built by the new Nix/Hydra system.
# It needs to be run in the root (base) conda environment with "python install-with-conda.py"
# It supports Linux and Windows, but Linux users should consider using the higher-quality
# Nix package manager instead of Conda.

# EDIT THIS:
# The name of the conda environment to create
CONDA_ENV_NAME = "artiq"
# The conda packages to download from hydra and install.
# Each entry is ("hydra build name", "conda package name"). Hydra builds are:
#  * main: core ARTIQ packages, including controllers for third-party devices
#  * sinara-systems: firmware and gateware builds for generic Sinara systems
CONDA_PACKAGES = [
    ("main",           "artiq"),
    ("main",           "artiq-board-kc705-nist_clock"),
    ("main",           "artiq-board-kasli-tester"),
    ("sinara-systems", "artiq-board-kasli-mitll")
]
# Set to False if you have already set up conda channels
ADD_CHANNELS = True

# PROXY: If you are behind a web proxy, configure it in your .condarc (as per
# the conda manual) and add it to the "curl" command below (add "--proxy
# http://webproxy.your.com:8080" with your values filled in)

# You should not need to modify the rest of the script below.

import os
import tempfile

def run(command):
    r = os.system(command)
    if r != 0:
        raise SystemExit("command '{}' returned non-zero exit status: {}".format(command, r))

if ADD_CHANNELS:
    run("conda config --prepend channels m-labs")
    run("conda config --append channels conda-forge")
run("conda install -y conda-build curl")

# A questionable conda decision is to ignore dependencies when installing .tar.bz2's directly.
# Work around it by creating a channel for our packages.
with tempfile.TemporaryDirectory() as channel_dir:
    print("Creating conda channel in {channel_dir}...".format(channel_dir=channel_dir))
    previous_dir = os.getcwd()
    os.chdir(channel_dir)
    try:
        os.mkdir("noarch")
        # curl -OJL won't take the correct filename and it will save the output as "conda".
        # wget --content-disposition is better-behaved but wget cannot be used on Windows.
        # Amazingly, conda doesn't break when package files are renamed, so we can get away
        # by generating our own names that don't contain the version number.
        for hydra_build, package in CONDA_PACKAGES:
            run("curl https://nixbld.m-labs.hk/job/artiq/{hydra_build}/conda-{package}/latest/download-by-type/file/conda -L -o noarch/{package}.tar.bz2"
                .format(hydra_build=hydra_build, package=package))
        run("conda index")

        # Creating the environment first with python 3.5 hits fewer bugs in conda's broken dependency solver.
        run("conda create -y -n {CONDA_ENV_NAME} python=3.5".format(CONDA_ENV_NAME=CONDA_ENV_NAME))
        for _, package in CONDA_PACKAGES:
            # Do not activate the environment yet - otherwise "conda install" may not find the SSL module anymore on Windows.
            # Installing into the environment from the outside works around this conda bug.
            run("conda install -y -n {CONDA_ENV_NAME} -c {channel_dir} {package}"
                .format(CONDA_ENV_NAME=CONDA_ENV_NAME, channel_dir=channel_dir, package=package))
    finally:
        os.chdir(previous_dir)
