#!/bin/bash

patch -p1 < ${RECIPE_DIR}/../../misc/llvmlite-add-all-targets.patch
PATH=/usr/local/llvm-or1k/bin:$PATH $PYTHON setup.py install
