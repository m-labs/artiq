#!/bin/bash

make -C $SRC_DIR/tools flterm
mkdir -p $PREFIX/bin
cp $SRC_DIR/tools/flterm $PREFIX/bin/
