#!/bin/bash
# Copyright (C) 2014, 2015 Robert Jordens <jordens@gmail.com>

export PATH=$HOME/miniconda/bin:$PATH
wget http://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh -O miniconda.sh
bash miniconda.sh -b -p $HOME/miniconda
hash -r
conda config --set always_yes yes --set changeps1 no
conda create -q -n py35 python=$TRAVIS_PYTHON_VERSION
source $HOME/miniconda/bin/activate py35
conda update -q conda
conda info -a
conda install conda-build jinja2
conda config --add channels https://conda.anaconda.org/m-labs/channel/dev
