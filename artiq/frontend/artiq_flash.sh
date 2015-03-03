#!/bin/bash

ARTIQ_PREFIX=$(python3 -c "import artiq; print(artiq.__path__[0])")
BIN_PREFIX=$ARTIQ_PREFIX/binaries

while getopts "bBrh" opt
do
	case $opt in
		b)
			FLASH_BITSTREAM=1
			;;
		B)
			FLASH_BIOS=1
			;;
		r)
			FLASH_RUNTIME=1
			;;
		*)
			echo "ARTIQ flashing tool"
			echo ""
			echo "To flash everything, do not use any command line option."
			echo ""
			echo "usage: $0 [-b] [-B] [-r] [-h]"
			echo "-b  Flash bitstream"
			echo "-B  Flash BIOS"
			echo "-r  Flash ARTIQ runtime"
			echo "-h  Show this help message"
			exit 1
			;;
	esac
done

if [ -z $@ ]
then
	FLASH_RUNTIME=1
	FLASH_BIOS=1
	FLASH_BITSTREAM=1
fi

check_return() {
	echo "Flashing failed, you may want to re-run the flashing tool."
	exit
}

xc3sprog -c papilio -R 2&>1 > /dev/null
if [ "$?" != "0" ]
then
		echo "Flashing failed because it seems you do not have permission to access the USB device."
		echo "To fix this you might want to add a udev rule by doing:"
		echo "$ sudo cp $ARTIQ_PREFIX/misc/99-ppro.rules /etc/udev/rules.d"
		echo "Then unplug/replug your device and try flashing again"
		exit
fi

trap check_return ERR

if [ "${FLASH_BITSTREAM}" == "1" ]
then
	echo "Flashing FPGA bitstream..."
	xc3sprog -v -c papilio -I$BIN_PREFIX/bscan_spi_lx9_papilio.bit $BIN_PREFIX/artiqminisoc-papilio_pro.bin:w:0x0:BIN
fi

if [ "${FLASH_BIOS}" == "1" ]
then
	echo "Flashing BIOS..."
	xc3sprog -v -c papilio -I$BIN_PREFIX/bscan_spi_lx9_papilio.bit $BIN_PREFIX/bios.bin:w:0x60000:BIN
fi

if [ "${FLASH_RUNTIME}" == "1" ]
then
	echo "Flashing ARTIQ runtime..."
	xc3sprog -v -c papilio -I$BIN_PREFIX/bscan_spi_lx9_papilio.bit $BIN_PREFIX/runtime.fbi:w:0x70000:BIN
fi
echo "Done."
xc3sprog -v -c papilio -R 2&>1 > /dev/null
