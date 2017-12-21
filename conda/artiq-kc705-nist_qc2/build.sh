#!/bin/bash

BUILD_SETTINGS_FILE=$HOME/.m-labs/build_settings.sh
[ -f $BUILD_SETTINGS_FILE ] && . $BUILD_SETTINGS_FILE

SOC_PREFIX=$PREFIX/lib/python3.5/site-packages/artiq/binaries/kc705-nist_qc2
mkdir -p $SOC_PREFIX

V=1 $PYTHON -m artiq.gateware.targets.kc705_dds -H nist_qc2
cp misoc_nist_qc2_kc705/gateware/top.bit $SOC_PREFIX
cp misoc_nist_qc2_kc705/software/bios/bios.bin $SOC_PREFIX
cp misoc_nist_qc2_kc705/software/runtime/runtime.fbi $SOC_PREFIX
