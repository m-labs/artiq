#!/bin/sh
# Copyright (C) 2014, 2015 M-Labs Limited
# Copyright (C) 2014, 2015 Robert Jordens <jordens@gmail.com>

wget http://sionneau.net/artiq/Xilinx/xilinx_ise_14.7_s3_s6.tar.gz.gpg
echo "$secret" | gpg --passphrase-fd 0 xilinx_ise_14.7_s3_s6.tar.gz.gpg
tar -C $HOME/ -xzf xilinx_ise_14.7_s3_s6.tar.gz
wget http://sionneau.net/artiq/Xilinx/Xilinx_Vivado_2015_1_k7.tar.gz.gpg
echo "$secret" | gpg --passphrase-fd 0 Xilinx_Vivado_2015_1_k7.tar.gz.gpg
tar -C $HOME/ -xzf Xilinx_Vivado_2015_1_k7.tar.gz

# Relocate Vivado from /opt to $HOME
for i in $(grep -Rsn "/opt/Xilinx" $HOME/Xilinx | cut -d':' -f1)
do
	sed -i -e "s!/opt!$HOME!g" $i
done

# Relocate ISE from /opt to $HOME
for i in $(grep -Rsn "/opt/Xilinx" $HOME/opt | cut -d':' -f1)
do
	sed -i -e "s!/opt/Xilinx!$HOME/opt/Xilinx!g" $i
done

wget http://sionneau.net/artiq/Xilinx/Xilinx.lic.gpg
echo "$secret" | gpg --passphrase-fd 0 Xilinx.lic.gpg
mkdir -p ~/.Xilinx
mv Xilinx.lic ~/.Xilinx/Xilinx.lic

git clone https://github.com/fallen/impersonate_macaddress
make -C impersonate_macaddress
# Tell mibuild where Xilinx toolchains are installed
# and feed it the mac address corresponding to the license
cat >> $HOME/.mlabs/build_settings.sh << EOF
MISOC_EXTRA_VIVADO_CMDLINE="-Ob vivado_path $HOME/Xilinx/Vivado"
MISOC_EXTRA_ISE_CMDLINE="-Ob ise_path $HOME/opt/Xilinx/"
export MACADDR=$macaddress
export LD_PRELOAD=$PWD/impersonate_macaddress/impersonate_macaddress.so
EOF
