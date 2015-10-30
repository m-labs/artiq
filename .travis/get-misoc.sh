#!/bin/sh

git clone --recursive https://github.com/m-labs/misoc $HOME/misoc
echo "export MSCDIR=$HOME/misoc" >> $HOME/.m-labs/build_settings.sh
