#!/bin/bash

BUILD_SETTINGS_FILE=$HOME/.m-labs/build_settings.sh
[ -f $BUILD_SETTINGS_FILE ] && . $BUILD_SETTINGS_FILE

SOC_PREFIX=$PREFIX/lib/python3.5/site-packages/artiq/binaries/kc705
mkdir -p $SOC_PREFIX/nist_qc2

SOC_ROOT=$PWD/soc

# build bitstream

(cd $MSCDIR; $PYTHON make.py -X $SOC_ROOT -t artiq_kc705 -s NIST_QC2 $MISOC_EXTRA_VIVADO_CMDLINE build-bitstream)
cp $MSCDIR/build/artiq_kc705-nist_qc2-kc705.bit $SOC_PREFIX/
wget http://sionneau.net/artiq/binaries/kc705/flash_proxy/bscan_spi_kc705.bit
mv bscan_spi_kc705.bit $SOC_PREFIX/

# build BIOS

(cd $MSCDIR; $PYTHON make.py -X $SOC_ROOT -t artiq_kc705 -s NIST_QC2 build-headers build-bios)
cp $MSCDIR/software/bios/bios.bin $SOC_PREFIX/

# build runtime

make -C soc/runtime clean runtime.fbi
cp soc/runtime/runtime.fbi $SOC_PREFIX/nist_qc2/
