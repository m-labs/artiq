#!/bin/bash

SOC_PREFIX=$SP_DIR/artiq/binaries/kasli-satellite
mkdir -p $SOC_PREFIX

V=1 $PYTHON -m artiq.gateware.targets.kasli -V satellite
cp artiq_kasli/satellite/gateware/top.bit $SOC_PREFIX
cp artiq_kasli/satellite/software/bootloader/bootloader.bin $SOC_PREFIX
cp artiq_kasli/satellite/software/satman/satman.{elf,fbi} $SOC_PREFIX
