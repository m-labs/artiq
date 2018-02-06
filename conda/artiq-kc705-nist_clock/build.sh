#!/bin/bash

SOC_PREFIX=$SP_DIR/artiq/binaries/kc705-nist_clock
mkdir -p $SOC_PREFIX

V=1 $PYTHON -m artiq.gateware.targets.kc705 -V nist_clock
cp artiq_kc705/nist_clock/gateware/top.bit $SOC_PREFIX
cp artiq_kc705/nist_clock/software/bootloader/bootloader.bin $SOC_PREFIX
cp artiq_kc705/nist_clock/software/runtime/runtime.{elf,fbi} $SOC_PREFIX
