#!/bin/bash

BUILD_SETTINGS_FILE=$HOME/.m-labs/build_settings.sh
[ -f $BUILD_SETTINGS_FILE ] && . $BUILD_SETTINGS_FILE

SOC_PREFIX=$PREFIX/lib/python3.5/site-packages/artiq/binaries/kc705-qc2
mkdir -p $SOC_PREFIX

$PYTHON -m artiq.gateware.targets.kc705 -H qc2 --toolchain vivado $MISOC_EXTRA_VIVADO_CMDLINE
cp misoc_nist_qc2_kc705/gateware/top.bit $SOC_PREFIX
cp misoc_nist_qc2_kc705/software/bios/bios.bin $SOC_PREFIX
cp misoc_nist_qc2_kc705/software/runtime/runtime.fbi $SOC_PREFIX

wget -P $SOC_PREFIX https://raw.githubusercontent.com/jordens/bscan_spi_bitstreams/master/bscan_spi_xc7k325t.bit
