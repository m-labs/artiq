#!/bin/bash

SOC_PREFIX=$PREFIX/lib/python3.5/site-packages/artiq/binaries/sayma_amc-standalone
mkdir -p $SOC_PREFIX

V=1 $PYTHON -m artiq.gateware.targets.sayma_amc_standalone --installed-rtm-csr-csv
cp misoc_standalone_sayma_amc/gateware/top.bit $SOC_PREFIX
cp misoc_standalone_sayma_amc/software/bios/bios.bin $SOC_PREFIX
cp misoc_standalone_sayma_amc/software/runtime/runtime.fbi $SOC_PREFIX
