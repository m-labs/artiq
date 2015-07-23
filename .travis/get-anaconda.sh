#!/bin/sh

export PATH=$HOME/miniconda/bin:$PATH
wget http://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh -O miniconda.sh
bash miniconda.sh -b -p $HOME/miniconda
hash -r
conda config --set always_yes yes --set changeps1 no
conda update -q conda
conda info -a
conda install conda-build jinja2
conda create -q -n py34 python=$TRAVIS_PYTHON_VERSION
conda config --add channels fallen
conda config --add channels https://conda.anaconda.org/fallen/channel/dev
