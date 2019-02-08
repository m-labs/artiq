#!/bin/bash

set -e

$PYTHON setup.py install \
  --prefix=$PREFIX \
  --single-version-externally-managed \
  --record=record.txt \
  --no-compile
