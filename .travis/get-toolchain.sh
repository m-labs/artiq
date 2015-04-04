#!/bin/sh

packages="https://people.phys.ethz.ch/~robertjo/artiq-dev/or1k-gcc_20141105-1_amd64.deb
https://people.phys.ethz.ch/~robertjo/artiq-dev/or1k-binutils_20141105-1_amd64.deb
http://us.archive.ubuntu.com/ubuntu/pool/universe/i/iverilog/iverilog_0.9.7-1_amd64.deb"

mkdir -p packages

for p in $packages
do
	wget $p
	pkg_name=$(echo $p | sed -e 's!.*/\(.*\)\.deb!\1\.deb!')
	dpkg -x $pkg_name packages
done

export PATH=$PWD/packages/usr/local/bin:$PWD/packages/usr/bin:$PATH
export LD_LIBRARY_PATH=$PWD/packages/usr/lib/x86_64-linux-gnu:$PWD/packages/usr/local/x86_64-unknown-linux-gnu/or1k-elf/lib:$LD_LIBRARY_PATH

echo -e "export LD_LIBRARY_PATH=$LD_LIBRARY_PATH" >> $HOME/.mlabs/build_settings.sh

or1k-elf-as --version
or1k-elf-gcc --version
clang --version
llvm-as --version || true
