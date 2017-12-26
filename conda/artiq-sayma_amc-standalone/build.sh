#!/bin/bash

SOC_PREFIX=$PREFIX/lib/python3.5/site-packages/artiq/binaries/sayma_amc-standalone
mkdir -p $SOC_PREFIX

V=1 $PYTHON -m artiq.gateware.targets.sayma_amc_standalone --rtm-csr-csv $SP_DIR/artiq/binaries/sayma_rtm/sayma_rtm_csr.csv
cp misoc_standalone_sayma_amc/gateware/top.bit $SOC_PREFIX
cp misoc_standalone_sayma_amc/software/bios/bios.bin $SOC_PREFIX
cp misoc_standalone_sayma_amc/software/runtime/runtime.{elf,fbi} $SOC_PREFIX
