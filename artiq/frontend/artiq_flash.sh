#!/bin/bash

set -e

ARTIQ_PREFIX=$(python3 -c "import artiq; print(artiq.__path__[0])")

# Default is kc705
BOARD=kc705

while getopts "bBrht:d:" opt
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
		t)
			if [ "$OPTARG" == "kc705" ]
			then
				BOARD=kc705
			elif [ "$OPTARG" == "pipistrello" ]
			then
				BOARD=pipistrello
			else
				echo "Supported targets (-t option) are:"
				echo "kc705 or pipistrello"
				exit 1
			fi
			;;
		d)
			if [ -d $OPTARG ]
			then
				BIN_PATH=$OPTARG
			else
				echo "You specified a non-existing directory: $OPTARG"
				exit 1
			fi
			;;
		*)
			echo "ARTIQ flashing tool"
			echo ""
			echo "To flash everything, do not use any of the -b|-B|-r option."
			echo ""
			echo "usage: $0 [-b] [-B] [-r] [-h] [-t kc705|pipistrello] [-d path]"
			echo "-b  Flash bitstream"
			echo "-B  Flash BIOS"
			echo "-r  Flash ARTIQ runtime"
			echo "-h  Show this help message"
			echo "-t  Target (kc705, pipistrello, default is: kc705)"
			echo "-d  Directory containing the binaries to be flashed"
			exit 1
			;;
	esac
done

function search_for_proxy()
{
	PROXY=$1 # The proxy name
	if [ -f $HOME/.migen/$PROXY ]
	then
		PROXY_PATH=$HOME/.migen/
	elif [ -f /usr/local/share/migen/$PROXY ]
	then
		PROXY_PATH=/usr/local/share/migen/
	elif [ -f /usr/share/migen/$PROXY ]
	then
		PROXY_PATH=/usr/share/migen/
	elif [ -f $BIN_PREFIX/$PROXY ]
	then
		PROXY_PATH=$BIN_PREFIX
	else
		echo "$BOARD flash proxy ($PROXY) not found."
		echo "Please put it in ~/.migen or /usr/local/share/migen or /usr/share/migen"
		echo "To get the flash proxy, follow the \"Install the required flash proxy bitstreams:\""
		echo "bullet point from http://m-labs.hk/artiq/manual/installing.html#preparing-the-core-device-fpga-board"
		exit 1
	fi
}

if ! [ -z "$BIN_PATH" ]
then
	BIN_PREFIX=$BIN_PATH
fi

if [ "$BOARD" == "kc705" ]
then
	UDEV_RULES=99-kc705.rules
	BITSTREAM=artiq_kc705-nist_qc1-kc705.bit
	CABLE=jtaghs1_fast
	PROXY=bscan_spi_kc705.bit
	BIOS_ADDR=0xaf0000
	RUNTIME_ADDR=0xb00000
	if [ -z "$BIN_PREFIX" ]; then BIN_PREFIX=$ARTIQ_PREFIX/binaries/kc705; fi
	search_for_proxy $PROXY
elif [ "$BOARD" == "pipistrello" ]
then
	UDEV_RULES=99-papilio.rules
	BITSTREAM=artiq_pipistrello-nist_qc1-pipistrello.bin
	CABLE=papilio
	PROXY=bscan_spi_lx45_csg324.bit
	BIOS_ADDR=0x170000
	RUNTIME_ADDR=0x180000
	if [ -z "$BIN_PREFIX" ]; then BIN_PREFIX=$ARTIQ_PREFIX/binaries/pipistrello; fi
	search_for_proxy $PROXY
fi

# Check if neither of -b|-B|-r have been used
if [ -z "$FLASH_RUNTIME" -a -z "$FLASH_BIOS" -a -z "$FLASH_BITSTREAM" ]
then
	FLASH_RUNTIME=1
	FLASH_BIOS=1
	FLASH_BITSTREAM=1
fi

check_return() {
	echo "Flashing failed, you may want to re-run the flashing tool."
	exit
}

xc3sprog -c $CABLE -R > /dev/null 2>&1
if [ "$?" != "0" ]
then
		echo "Flashing failed. Maybe you do not have permission to access the USB device?"
		echo "To fix this you might want to add a udev rule by doing:"
		echo "$ sudo cp $ARTIQ_PREFIX/misc/$UDEV_RULES /etc/udev/rules.d"
		echo "Then unplug/replug your device and try flashing again"
		exit
fi

trap check_return ERR

if [ "${FLASH_BITSTREAM}" == "1" ]
then
	echo "Flashing FPGA bitstream..."
	xc3sprog -v -c $CABLE -I$PROXY_PATH/$PROXY $BIN_PREFIX/$BITSTREAM:w:0x0:BIN
fi

if [ "${FLASH_BIOS}" == "1" ]
then
	echo "Flashing BIOS..."
	xc3sprog -v -c $CABLE -I$PROXY_PATH/$PROXY $BIN_PREFIX/bios.bin:w:$BIOS_ADDR:BIN
fi

if [ "${FLASH_RUNTIME}" == "1" ]
then
	echo "Flashing ARTIQ runtime..."
	xc3sprog -v -c $CABLE -I$PROXY_PATH/$PROXY $BIN_PREFIX/runtime.fbi:w:$RUNTIME_ADDR:BIN
fi
echo "Done."
xc3sprog -v -c $CABLE -R > /dev/null 2>&1
