#!/bin/sh

sudo add-apt-repository -y ppa:ubuntu-toolchain-r/test
sudo apt-add-repository -y "deb http://www.phys.ethz.ch/~robertjo/artiq-dev ./"
sudo apt-add-repository -y "deb http://archive.ubuntu.com/ubuntu saucy main universe"
sudo apt-get -qq --force-yes -y update
sudo apt-get install --force-yes -y gcc-4.7 g++-4.7 artiq-dev
or1k-elf-as --version
or1k-elf-gcc --version
clang --version
llvm-as --version || true
