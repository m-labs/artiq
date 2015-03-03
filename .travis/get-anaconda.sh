#!/bin/sh

wget http://repo.continuum.io/miniconda/Miniconda3-3.7.3-Linux-x86_64.sh -O miniconda.sh
bash miniconda.sh -b -p $HOME/miniconda
hash -r
conda config --set always_yes yes --set changeps1 no
conda update -q conda
conda install conda-build jinja2
conda info -a
conda create -q -n py34 python=$TRAVIS_PYTHON_VERSION $@
conda config --add channels fallen
