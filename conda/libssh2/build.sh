#!/bin/bash

mkdir build
cd build
cmake .. -DCMAKE_INSTALL_PREFIX=$PREFIX -DOPENSSL_ROOT_DIR=$PREFIX
make -j2
make install
