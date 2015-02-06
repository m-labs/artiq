#!/bin/sh

sudo apt-get install --force-yes -y iverilog
pip install --src . -e 'git+https://github.com/m-labs/migen.git@master#egg=migen'
mkdir vpi && iverilog-vpi --name=vpi/migensim migen/vpi/main.c migen/vpi/ipc.c
git clone --recursive https://github.com/m-labs/misoc
