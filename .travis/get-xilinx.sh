#!/bin/sh

wget http://www.phys.ethz.ch/~robertjo/xilinx_ise_14.7_s3_s6.tar.gz.gpg
echo "$secret" | gpg --passphrase-fd 0 xilinx_ise_14.7_s3_s6.tar.gz.gpg
sudo tar -C / -xzf xilinx_ise_14.7_s3_s6.tar.gz
wget http://www.phys.ethz.ch/~robertjo/xilinx_webpack.lic.gpg
echo "$secret" | gpg --passphrase-fd 0 xilinx_webpack.lic.gpg
mkdir ~/.Xilinx
mv xilinx_webpack.lic ~/.Xilinx/Xilinx.lic
