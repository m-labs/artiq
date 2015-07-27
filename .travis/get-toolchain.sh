#!/bin/sh

packages="http://us.archive.ubuntu.com/ubuntu/pool/universe/i/iverilog/iverilog_0.9.7-1_amd64.deb"
archives="http://fehu.whitequark.org/files/binutils-or1k.tbz2 http://fehu.whitequark.org/files/llvm-or1k.tbz2"

mkdir -p packages

for p in $packages
do
	wget $p
	pkg_name=$(echo $p | sed -e 's!.*/\(.*\)\.deb!\1\.deb!')
	dpkg -x $pkg_name packages
done

for a in $archives
do
  wget $a
  (cd packages && tar xf ../$(basename $a))
done

export PATH=$PWD/packages/usr/local/llvm-or1k/bin:$PWD/packages/usr/local/bin:$PWD/packages/usr/bin:$PATH
export LD_LIBRARY_PATH=$PWD/packages/usr/lib/x86_64-linux-gnu:$PWD/packages/usr/local/x86_64-unknown-linux-gnu/or1k-elf/lib:$LD_LIBRARY_PATH

echo "export LD_LIBRARY_PATH=$LD_LIBRARY_PATH" >> $HOME/.mlabs/build_settings.sh
echo "export PATH=$PWD/packages/usr/local/llvm-or1k/bin:$PATH" >> $HOME/.mlabs/build_settings.sh

or1k-linux-as --version
llc --version
clang --version
