#!/bin/bash

mkdir build
cd build
cmake .. -DCMAKE_INSTALL_PREFIX=$PREFIX
make -j2
make install
