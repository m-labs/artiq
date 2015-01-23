#!/bin/bash
export CFLAGS="-I$PREFIX/include -L$PREFIX/lib"
./configure \
--prefix=$PREFIX \
--disable-static \
--enable-warnings \
--enable-ft \
--enable-ps \
--enable-pdf \
--enable-svg \
--disable-gtk-doc
make
make install
rm -rf $PREFIX/share
# vim:set ts=8 sw=4 sts=4 tw=78 et:
