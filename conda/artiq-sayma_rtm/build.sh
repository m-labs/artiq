#!/bin/bash

BUILD_SETTINGS_FILE=$HOME/.m-labs/build_settings.sh
[ -f $BUILD_SETTINGS_FILE ] && . $BUILD_SETTINGS_FILE

SOC_PREFIX=$PREFIX/lib/python3.5/site-packages/artiq/binaries/sayma_rtm
mkdir -p $SOC_PREFIX

$PYTHON -m artiq.gateware.targets.sayma_rtm
cp artiq_sayma_rtm/top.bit $SOC_PREFIX
cp artiq_sayma_rtm/sayma_rtm_csr.csv $SOC_PREFIX
