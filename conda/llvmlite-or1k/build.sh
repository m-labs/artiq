#!/bin/bash

patch -p1 < ${RECIPE_DIR}/../../patches/llvmlite/0001-add-all-targets.patch
PATH=/usr/local/llvm-or1k/bin:$PATH $PYTHON setup.py install
