#!/bin/bash

ARTIQ_PREFIX=$PREFIX/lib/python3.5/site-packages/artiq

$PYTHON setup.py install --single-version-externally-managed --record=record.txt
