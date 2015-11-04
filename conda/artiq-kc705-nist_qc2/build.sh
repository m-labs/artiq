#!/bin/bash

BUILD_SETTINGS_FILE=$HOME/.m-labs/build_settings.sh
[ -f $BUILD_SETTINGS_FILE ] && . $BUILD_SETTINGS_FILE

SOC_PREFIX=$PREFIX/lib/python3.5/site-packages/artiq/binaries/kc705-qc2
mkdir -p $SOC_PREFIX

$PYTHON -m artiq.gateware.targets.kc705 -H qc2 $MISOC_EXTRA_ISE_CMDLINE
cp misoc_nist_qc2_kc705/gateware/top.bit $SOC_PREFIX
cp misoc_nist_qc2_kc705/software/bios/bios.bin $SOC_PREFIX
cp misoc_nist_qc2_kc705/software/runtime/runtime.fbi $SOC_PREFIX

wget http://sionneau.net/artiq/binaries/kc705/flash_proxy/bscan_spi_kc705.bit
mv bscan_spi_kc705.bit $SOC_PREFIX
