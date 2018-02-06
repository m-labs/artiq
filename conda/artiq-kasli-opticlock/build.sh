#!/bin/bash

SOC_PREFIX=$SP_DIR/artiq/binaries/kasli-opticlock
mkdir -p $SOC_PREFIX

V=1 $PYTHON -m artiq.gateware.targets.kasli -V opticlock
cp artiq_kasli/opticlock/gateware/top.bit $SOC_PREFIX
cp artiq_kasli/opticlock/software/bootloader/bootloader.bin $SOC_PREFIX
cp artiq_kasli/opticlock/software/runtime/runtime.{elf,fbi} $SOC_PREFIX
