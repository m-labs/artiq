#!/bin/bash

set -e

$PYTHON setup.py install \
  --install-lib=$SP_DIR \
  --single-version-externally-managed \
  --record=record.txt \
  --no-compile
