patch -p1 < $RECIPE_DIR/../../misc/binutils-2.25.1-or1k-R_PCREL-pcrel_offset.patch
mkdir build
cd build
../configure --target=or1k-linux --prefix=$PREFIX
make -j2
make install
