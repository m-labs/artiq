#!/bin/bash

SOC_PREFIX=$PREFIX/lib/python3.5/site-packages/artiq/binaries/kc705-nist_clock
mkdir -p $SOC_PREFIX

V=1 $PYTHON -m artiq.gateware.targets.kc705_dds -H nist_clock
cp misoc_nist_clock_kc705/gateware/top.bit $SOC_PREFIX
cp misoc_nist_clock_kc705/software/bios/bios.bin $SOC_PREFIX
cp misoc_nist_clock_kc705/software/runtime/runtime.fbi $SOC_PREFIX
