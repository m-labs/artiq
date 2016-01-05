#!/bin/bash

BUILD_SETTINGS_FILE=$HOME/.m-labs/build_settings.sh
[ -f $BUILD_SETTINGS_FILE ] && . $BUILD_SETTINGS_FILE

SOC_PREFIX=$PREFIX/lib/python3.5/site-packages/artiq/binaries/pipistrello-qc1
mkdir -p $SOC_PREFIX

$PYTHON -m artiq.gateware.targets.pipistrello $MISOC_EXTRA_ISE_CMDLINE
cp misoc_nist_qc1_pipistrello/gateware/top.bit $SOC_PREFIX
cp misoc_nist_qc1_pipistrello/software/bios/bios.bin $SOC_PREFIX
cp misoc_nist_qc1_pipistrello/software/runtime/runtime.fbi $SOC_PREFIX

wget https://github.com/jordens/bscan_spi_bitstreams/blob/master/bscan_spi_xc6slx45.bit?raw=true -O bscan_spi_xc6slx45.bit
mv bscan_spi_xc6slx45.bit $SOC_PREFIX
