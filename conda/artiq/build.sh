#!/bin/bash

ARTIQ_PREFIX=$PREFIX/lib/python3.5/site-packages/artiq

$PYTHON setup.py install --single-version-externally-managed --record=record.txt

# install scripts

cp artiq/frontend/artiq_flash.sh $PREFIX/bin

# install udev rules

mkdir -p $ARTIQ_PREFIX/misc
cp misc/99-papilio.rules $ARTIQ_PREFIX/misc/
cp misc/99-kc705.rules $ARTIQ_PREFIX/misc/
