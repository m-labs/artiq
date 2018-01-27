#!/bin/bash

SOC_PREFIX=$PREFIX/lib/python3.5/site-packages/artiq/binaries/sayma-standalone
mkdir -p $SOC_PREFIX

$PYTHON -m artiq.gateware.targets.sayma_rtm
cp artiq_sayma/rtm_gateware/rtm.bit $SOC_PREFIX

$PYTHON -m artiq.gateware.targets.sayma_amc -V standalone \
  --rtm-csr-csv artiq_sayma/rtm/sayma_rtm_csr.csv
cp artiq_sayma/gateware/top.bit $SOC_PREFIX
cp artiq_sayma/software/bootloader/bootloader.bin $SOC_PREFIX
cp artiq_sayma/software/runtime/runtime.{elf,fbi} $SOC_PREFIX
