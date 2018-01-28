#!/bin/bash

SOC_PREFIX=$SP_DIR/artiq/binaries/kasli-opticlock
mkdir -p $SOC_PREFIX

V=1 $PYTHON -m artiq.gateware.targets.kasli -V opticlock
cp misoc_opticlock_kasli/gateware/top.bit $SOC_PREFIX
cp misoc_opticlock_kasli/software/bootloader/bootloader.bin $SOC_PREFIX
cp misoc_opticlock_kasli/software/runtime/runtime.{elf,fbi} $SOC_PREFIX
