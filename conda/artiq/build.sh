#!/bin/bash

BUILD_SETTINGS_FILE=$HOME/.mlabs/build_settings.sh

if [ -f $BUILD_SETTINGS_FILE ]
then
	source $BUILD_SETTINGS_FILE
fi

ARTIQ_GUI=1 $PYTHON setup.py install --single-version-externally-managed --record=record.txt
git clone --recursive https://github.com/m-labs/misoc
export MSCDIR=$SRC_DIR/misoc

ARTIQ_PREFIX=$PREFIX/lib/python3.4/site-packages/artiq
BIN_PREFIX=$ARTIQ_PREFIX/binaries/
mkdir -p $ARTIQ_PREFIX/misc
mkdir -p $BIN_PREFIX/kc705 $BIN_PREFIX/pipistrello

# build for KC705

cd $SRC_DIR/misoc; $PYTHON make.py -X ../soc -t artiq_kc705 build-headers build-bios; cd -
make -C soc/runtime clean runtime.fbi
cd $SRC_DIR/misoc; $PYTHON make.py -X ../soc -t artiq_kc705 $MISOC_EXTRA_VIVADO_CMDLINE build-bitstream; cd -

# install KC705 binaries

cp soc/runtime/runtime.fbi $BIN_PREFIX/kc705/
cp $SRC_DIR/misoc/software/bios/bios.bin $BIN_PREFIX/kc705/
cp $SRC_DIR/misoc/build/artiq_kc705-nist_qc1-kc705.bit $BIN_PREFIX/kc705/
wget http://sionneau.net/artiq/binaries/kc705/flash_proxy/bscan_spi_kc705.bit
mv bscan_spi_kc705.bit $BIN_PREFIX/kc705/

# build for Pipistrello

cd $SRC_DIR/misoc; $PYTHON make.py -X ../soc -t artiq_pipistrello build-headers build-bios; cd -
make -C soc/runtime clean runtime.fbi
cd $SRC_DIR/misoc; $PYTHON make.py -X ../soc -t artiq_pipistrello $MISOC_EXTRA_ISE_CMDLINE build-bitstream; cd -

# install Pipistrello binaries

cp soc/runtime/runtime.fbi $BIN_PREFIX/pipistrello/
cp $SRC_DIR/misoc/software/bios/bios.bin $BIN_PREFIX/pipistrello/
cp $SRC_DIR/misoc/build/artiq_pipistrello-nist_qc1-pipistrello.bit $BIN_PREFIX/pipistrello/
wget http://www.phys.ethz.ch/~robertjo/bscan_spi_lx45_csg324.bit
mv bscan_spi_lx45_csg324.bit $BIN_PREFIX/pipistrello/

cp artiq/frontend/artiq_flash.sh $PREFIX/bin

# misc
cp misc/99-papilio.rules $ARTIQ_PREFIX/misc/
cp misc/99-kc705.rules $ARTIQ_PREFIX/misc/
