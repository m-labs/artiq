#!/bin/bash

SOC_PREFIX=$SP_DIR/artiq/binaries/kc705-nist_qc2
mkdir -p $SOC_PREFIX

V=1 $PYTHON -m artiq.gateware.targets.kc705 -V nist_qc2
cp misoc_nist_qc2_kc705/gateware/top.bit $SOC_PREFIX
cp misoc_nist_qc2_kc705/software/bootloader/bootloader.bin $SOC_PREFIX
cp misoc_nist_qc2_kc705/software/runtime/runtime.{elf,fbi} $SOC_PREFIX
