#!/bin/bash

cd tools
git clone https://github.com/openrisc/clang-or1k clang
cd ..
mkdir build
cd build
cmake .. -DCMAKE_INSTALL_PREFIX=$PREFIX -DLLVM_TARGETS_TO_BUILD="OR1K;X86" -DCMAKE_BUILD_TYPE=Debug
make -j2
make install
