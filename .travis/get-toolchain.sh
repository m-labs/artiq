#!/bin/sh

packages="http://us.archive.ubuntu.com/ubuntu/pool/universe/i/iverilog/iverilog_0.9.7-1_amd64.deb"

mkdir -p packages

for p in $packages
do
	wget $p
	pkg_name=$(echo $p | sed -e 's!.*/\(.*\)\.deb!\1\.deb!')
	dpkg -x $pkg_name packages
done

echo "export LD_LIBRARY_PATH=$PWD/packages/usr/lib/x86_64-linux-gnu" >> $HOME/.m-labs/build_settings.sh
echo "export PATH=$PWD/packages/usr/bin:\$PATH" >> $HOME/.m-labs/build_settings.sh
