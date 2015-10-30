#!/usr/bin/env python
# conda-build requires all scripts to have a python shebang.
# see https://github.com/conda/conda-build/blob/6921f067a/conda_build/noarch_python.py#L36-L38

def run(script):
		import sys, tempfile, subprocess
		file = tempfile.NamedTemporaryFile(mode='w+t', suffix='sh')
		file.write(script)
		file.flush()
		subprocess.run(["/bin/bash", file.name] + sys.argv[1:])
		file.close()

run("""
# exit on error
set -e
# print commands
#set -x

ARTIQ_PREFIX=$(python3 -c "import artiq; print(artiq.__path__[0])")

# Default is kc705
BOARD=kc705
# Default mezzanine board is nist_qc1
MEZZANINE_BOARD=nist_qc1

while getopts "bBrht:d:f:m:" opt
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
		f)
			if [ -f $OPTARG ]
			then
				FILENAME=$OPTARG
			else
				echo "You specified a non-existing file to flash: $OPTARG"
				exit 1
			fi
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
		m)
			if [ "$OPTARG" == "nist_qc1" ]
			then
				MEZZANINE_BOARD=nist_qc1
			elif [ "$OPTARG" == "nist_qc2" ]
			then
				MEZZANINE_BOARD=nist_qc2
			else
				echo "KC705 mezzanine board is either nist_qc1 or nist_qc2"
				exit 1
			fi
			;;
		*)
			echo "ARTIQ flashing tool"
			echo ""
			echo "To flash everything, do not use any of the -b|-B|-r option."
			echo ""
			echo "usage: artiq_flash.sh [-b] [-B] [-r] [-h] [-m nist_qc1|nist_qc2] [-t kc705|pipistrello] [-d path] [-f path]"
			echo "-b  Flash bitstream"
			echo "-B  Flash BIOS"
			echo "-r  Flash ARTIQ runtime"
			echo "-h  Show this help message"
			echo "-t  Target (kc705, pipistrello, default is: kc705)"
			echo "-m  Mezzanine board (nist_qc1, nist_qc2, default is: nist_qc1)"
			echo "-f  Flash storage image generated with artiq_mkfs"
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
	BITSTREAM=artiq_kc705-${MEZZANINE_BOARD}-kc705.bit
	CABLE=jtaghs1_fast
	PROXY=bscan_spi_kc705.bit
	BIOS_ADDR=0xaf0000
	RUNTIME_ADDR=0xb00000
	RUNTIME_FILE=runtime.fbi
	FS_ADDR=0xb40000
	if [ -z "$BIN_PREFIX" ]
	then
		RUNTIME_FILE=${MEZZANINE_BOARD}/runtime.fbi
		BIN_PREFIX=$ARTIQ_PREFIX/binaries/kc705
	fi
	search_for_proxy $PROXY
elif [ "$BOARD" == "pipistrello" ]
then
	UDEV_RULES=99-papilio.rules
	BITSTREAM=artiq_pipistrello-nist_qc1-pipistrello.bit
	CABLE=papilio
	PROXY=bscan_spi_lx45_csg324.bit
	BIOS_ADDR=0x170000
	RUNTIME_ADDR=0x180000
	RUNTIME_FILE=runtime.fbi
	FS_ADDR=0x1c0000
	if [ -z "$BIN_PREFIX" ]; then BIN_PREFIX=$ARTIQ_PREFIX/binaries/pipistrello; fi
	search_for_proxy $PROXY
fi

# Check if neither of -b|-B|-r have been used
if [ -z "$FLASH_RUNTIME" -a -z "$FLASH_BIOS" -a -z "$FLASH_BITSTREAM" -a -z "$FILENAME" ]
then
	FLASH_RUNTIME=1
	FLASH_BIOS=1
	FLASH_BITSTREAM=1
fi

set +e
xc3sprog -c $CABLE -R > /dev/null 2>&1
STATUS=$?
set -e
if [ "$STATUS" == "127" ]
then
		echo "xc3sprog not found. Please install it or check your PATH."
		exit
fi
if [ "$STATUS" != "0" ]
then
		echo "Failed to connect to FPGA."
		echo "Maybe you do not have permission to access the USB device?"
		echo "To fix this you might want to add a udev rule by doing:"
		echo "$ sudo cp $ARTIQ_PREFIX/misc/$UDEV_RULES /etc/udev/rules.d"
		echo "Then unplug/replug your device and try flashing again"
		echo
		echo "Other reason could be that you chosed the wrong target"
		echo "Please make sure you used the correct -t option (currently: $BOARD)"
		exit
fi

if [ ! -z "$FILENAME" ]
then
	echo "Flashing file $FILENAME at address $FS_ADDR"
	xc3sprog -v -c $CABLE -I$PROXY_PATH/$PROXY $FILENAME:w:$FS_ADDR:BIN
fi

if [ "${FLASH_BITSTREAM}" == "1" ]
then
	echo "Flashing FPGA bitstream..."
	xc3sprog -v -c $CABLE -I$PROXY_PATH/$PROXY $BIN_PREFIX/$BITSTREAM:w:0x0:BIT
fi

if [ "${FLASH_BIOS}" == "1" ]
then
	echo "Flashing BIOS..."
	xc3sprog -v -c $CABLE -I$PROXY_PATH/$PROXY $BIN_PREFIX/bios.bin:w:$BIOS_ADDR:BIN
fi

if [ "${FLASH_RUNTIME}" == "1" ]
then
	echo "Flashing ARTIQ runtime..."
	xc3sprog -v -c $CABLE -I$PROXY_PATH/$PROXY $BIN_PREFIX/${RUNTIME_FILE}:w:$RUNTIME_ADDR:BIN
fi
echo "Done."
xc3sprog -v -c $CABLE -R > /dev/null 2>&1
""")
