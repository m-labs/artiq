#!/bin/bash

set -e

$PYTHON setup.py install \
  --prefix=$SP_DIR \
  --single-version-externally-managed \
  --record=record.txt \
  --no-compile
