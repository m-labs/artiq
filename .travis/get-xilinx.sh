#!/bin/sh

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

# Tell mibuild where Vivado is installed
echo "MISOC_EXTRA_VIVADO_CMDLINE=\"-Ob vivado_path $HOME/Xilinx/Vivado\"" >> $HOME/.mlabs/build_settings.sh
echo "MISOC_EXTRA_ISE_CMDLINE=\"-Ob ise_path $HOME/opt/Xilinx/\"" >> $HOME/.mlabs/build_settings.sh

# Lie to Vivado by hooking the ioctl used to retrieve mac address for license verification
git clone https://github.com/fallen/impersonate_macaddress
make -C impersonate_macaddress
echo "export MACADDR=$macaddress" >> $HOME/.mlabs/build_settings.sh
echo "export LD_PRELOAD=$PWD/impersonate_macaddress/impersonate_macaddress.so" >> $HOME/.mlabs/build_settings.sh
