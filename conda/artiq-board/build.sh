#!/bin/bash

set -e

SOC_PREFIX=$PREFIX/site-packages/artiq/binaries/${ARTIQ_TARGET}-${ARTIQ_VARIANT}
mkdir -p ${SOC_PREFIX}

V=1 $PYTHON -m artiq.gateware.targets.${ARTIQ_TARGET} -V ${ARTIQ_VARIANT}
cp artiq_${ARTIQ_TARGET}/${ARTIQ_VARIANT}/gateware/top.bit ${SOC_PREFIX}
cp artiq_${ARTIQ_TARGET}/${ARTIQ_VARIANT}/software/bootloader/bootloader.bin ${SOC_PREFIX}
if [ -e artiq_${ARTIQ_TARGET}/${ARTIQ_VARIANT}/software/runtime ]
then cp artiq_${ARTIQ_TARGET}/${ARTIQ_VARIANT}/software/runtime/runtime.{elf,fbi} ${SOC_PREFIX}
else cp artiq_${ARTIQ_TARGET}/${ARTIQ_VARIANT}/software/satman/satman.{elf,fbi} ${SOC_PREFIX}
fi
