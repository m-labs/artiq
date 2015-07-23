#!/bin/bash

patch -p1 < ${RECIPE_DIR}/../../misc/llvmlite-add-all-targets.patch
patch -p1 < ${RECIPE_DIR}/../../misc/llvmlite-rename.patch
patch -p1 < ${RECIPE_DIR}/../../misc/llvmlite-build-as-debug-on-windows.patch
PATH=/usr/local/llvm-or1k/bin:$PATH $PYTHON setup.py install
