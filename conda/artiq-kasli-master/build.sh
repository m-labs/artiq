#!/bin/bash

SOC_PREFIX=$SP_DIR/artiq/binaries/kasli-master
mkdir -p $SOC_PREFIX

V=1 $PYTHON -m artiq.gateware.targets.kasli -V master
cp artiq_kasli/master/gateware/top.bit $SOC_PREFIX
cp artiq_kasli/master/software/bootloader/bootloader.bin $SOC_PREFIX
cp artiq_kasli/master/software/runtime/runtime.{elf,fbi} $SOC_PREFIX
