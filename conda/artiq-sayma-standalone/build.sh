#!/bin/bash

RTM_PREFIX=$SP_DIR/artiq/binaries/sayma_rtm

SOC_PREFIX=$SP_DIR/artiq/binaries/sayma-standalone
mkdir -p $SOC_PREFIX

$PYTHON -m artiq.gateware.targets.sayma_amc -V standalone \
  --rtm-csr-csv $RTM_PREFIX/rtm_csr.csv
cp artiq_sayma/standalone/gateware/top.bit $SOC_PREFIX
cp artiq_sayma/standalone/software/bootloader/bootloader.bin $SOC_PREFIX
cp artiq_sayma/standalone/software/runtime/runtime.{elf,fbi} $SOC_PREFIX
cp $RTM_PREFIX/rtm.bit $SOC_PREFIX
