#!/bin/bash

SOC_PREFIX=$PREFIX/site-packages/artiq/binaries/${ARTIQ_TARGET}-${ARTIQ_VARIANT}
mkdir -p ${SOC_PREFIX}

if [ "${ARTIQ_VARIANT}" = "phaser" ]; then
  V=1 $PYTHON -m artiq.gateware.targets.kc705_phaser --toolchain vivado $MISOC_EXTRA_VIVADO_CMDLINE
else
  V=1 $PYTHON -m artiq.gateware.targets.kc705_dds -H ${ARTIQ_VARIANT} --toolchain vivado $MISOC_EXTRA_VIVADO_CMDLINE
fi
cp -v misoc_${ARTIQ_VARIANT}_kc705/gateware/top.bit $SOC_PREFIX
cp -v misoc_${ARTIQ_VARIANT}_kc705/software/bios/bios.bin $SOC_PREFIX
cp -v misoc_${ARTIQ_VARIANT}_kc705/software/runtime/runtime.{elf,fbi} $SOC_PREFIX

wget -P $SOC_PREFIX https://raw.githubusercontent.com/jordens/bscan_spi_bitstreams/single-tap/bscan_spi_xc7k325t.bit
