#!/bin/bash
TERM=xterm ./autogen.sh
export CFLAGS="-L$PREFIX/lib -I$PREFIX/include"
./configure --prefix=$PREFIX
make
make install
