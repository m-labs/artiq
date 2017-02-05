#!/bin/bash

BUILD_SETTINGS_FILE=$HOME/.m-labs/build_settings.sh
[ -f $BUILD_SETTINGS_FILE ] && . $BUILD_SETTINGS_FILE

SOC_PREFIX=$PREFIX/lib/python3.5/site-packages/artiq/binaries/pipistrello-demo
mkdir -p $SOC_PREFIX

V=1 $PYTHON -m artiq.gateware.targets.pipistrello $MISOC_EXTRA_ISE_CMDLINE
cp misoc_demo_pipistrello/gateware/top.bit $SOC_PREFIX
cp misoc_demo_pipistrello/software/bios/bios.bin $SOC_PREFIX
cp misoc_demo_pipistrello/software/runtime/runtime.fbi $SOC_PREFIX

wget -P $SOC_PREFIX https://raw.githubusercontent.com/jordens/bscan_spi_bitstreams/master/bscan_spi_xc6slx45.bit
