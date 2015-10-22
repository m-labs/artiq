#!/bin/bash

BUILD_SETTINGS_FILE=$HOME/.m-labs/build_settings.sh
[ -f $BUILD_SETTINGS_FILE ] && . $BUILD_SETTINGS_FILE

SOC_PREFIX=$PREFIX/lib/python3.5/site-packages/artiq/binaries/pipistrello
mkdir -p $SOC_PREFIX

SOC_ROOT=$PWD/soc

# build bitstream

(cd $MSCDIR; $PYTHON make.py -X $SOC_ROOT -t artiq_pipistrello $MISOC_EXTRA_ISE_CMDLINE build-bitstream)
cp $MSCDIR/build/artiq_pipistrello-nist_qc1-pipistrello.bit $SOC_PREFIX/
wget https://people.phys.ethz.ch/~robertjo/bscan_spi_lx45_csg324.bit
mv bscan_spi_lx45_csg324.bit $SOC_PREFIX/

# build BIOS

(cd $MSCDIR; $PYTHON make.py -X $SOC_ROOT -t artiq_pipistrello build-headers build-bios)
cp $MSCDIR/software/bios/bios.bin $SOC_PREFIX/

# build runtime

make -C soc/runtime clean runtime.fbi
cp soc/runtime/runtime.fbi $SOC_PREFIX/
