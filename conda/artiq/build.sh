#!/bin/bash

ARTIQ_GUI=1 $PYTHON setup.py install --single-version-externally-managed --record=record.txt
git clone --recursive https://github.com/m-labs/misoc
git clone https://github.com/GadgetFactory/Papilio-Loader
export MSCDIR=$SRC_DIR/misoc
cd $SRC_DIR/misoc; python make.py -X ../soc -t artiq_ppro build-headers build-bios; cd -
make -C soc/runtime runtime.fbi
cd $SRC_DIR/misoc; python make.py -X $SRC_DIR/soc -t  artiq_ppro build-bitstream; cd -
ARTIQ_PREFIX=$PREFIX/lib/python3.4/site-packages/artiq
BIN_PREFIX=$ARTIQ_PREFIX/binaries
mkdir -p $ARTIQ_PREFIX/misc
cp misc/99-ppro.rules $ARTIQ_PREFIX/misc/
mkdir -p $BIN_PREFIX
cp $SRC_DIR/misoc/build/artiq_ppro-up-papilio_pro.bin $BIN_PREFIX/
cp $SRC_DIR/misoc/software/bios/bios.bin $BIN_PREFIX/
cp soc/runtime/runtime.fbi $BIN_PREFIX/
cp artiq/frontend/artiq_flash.sh $PREFIX/bin
cp Papilio-Loader/xc3sprog/trunk/bscan_spi/bscan_spi_lx9_papilio.bit $BIN_PREFIX/
