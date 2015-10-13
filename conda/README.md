Uploading conda packages (Python 3.5)
=====================================

Preparing:

  1. [Install miniconda][miniconda]
  2. `conda update -q conda`
  3. `conda install conda-build`
  4. `conda create -q -n py35 python=3.5`
  5. `conda config --add channels https://conda.anaconda.org/m-labs/channel/dev`

Building:

  1. `source activate py35`
  2. `conda build pkgname --python 3.5`; this command displays a path to the freshly built package
  3. `anaconda upload <package> -c main -c dev`

[miniconda]: http://conda.pydata.org/docs/install/quick.html#linux-miniconda-install
