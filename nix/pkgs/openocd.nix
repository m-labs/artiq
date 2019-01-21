{ stdenv, fetchFromGitHub, autoreconfHook, libftdi, libusb1, pkgconfig, hidapi }:

stdenv.mkDerivation rec {
  name = "openocd-${version}";
  version = "0.10.0";

  src = fetchFromGitHub {
    owner = "m-labs";
    repo = "openocd";
    fetchSubmodules = true;
    rev = "c383a57adcff332b2c5cf8d55a84626285b42c2c";
    sha256 = "0xlj9cs72acx3zqagvr7f1c0v6lnqhl8fgrlhgmhmvk5n9knk492";
  };

  nativeBuildInputs = [ pkgconfig ];
  buildInputs = [ autoreconfHook libftdi libusb1 hidapi ];

  configureFlags = [
    "--enable-jtag_vpi"
    "--enable-usb_blaster_libftdi"
    "--enable-amtjtagaccel"
    "--enable-gw16012"
    "--enable-presto_libftdi"
    "--enable-openjtag_ftdi"
    "--enable-oocd_trace"
    "--enable-buspirate"
    "--enable-sysfsgpio"
    "--enable-remote-bitbang"
  ];

  NIX_CFLAGS_COMPILE = [
    "-Wno-implicit-fallthrough"
    "-Wno-format-truncation"
    "-Wno-format-overflow"
  ];

  postInstall = ''
    mkdir -p "$out/etc/udev/rules.d"
    rules="$out/share/openocd/contrib/60-openocd.rules"
    if [ ! -f "$rules" ]; then
        echo "$rules is missing, must update the Nix file."
        exit 1
    fi
    ln -s "$rules" "$out/etc/udev/rules.d/"
  '';

  meta = with stdenv.lib; {
    description = "Free and Open On-Chip Debugging, In-System Programming and Boundary-Scan Testing";
    longDescription = ''
      OpenOCD provides on-chip programming and debugging support with a layered
      architecture of JTAG interface and TAP support, debug target support
      (e.g. ARM, MIPS), and flash chip drivers (e.g. CFI, NAND, etc.).  Several
      network interfaces are available for interactiving with OpenOCD: HTTP,
      telnet, TCL, and GDB.  The GDB server enables OpenOCD to function as a
      "remote target" for source-level debugging of embedded systems using the
      GNU GDB program.
    '';
    homepage = http://openocd.sourceforge.net/;
    license = licenses.gpl2Plus;
    #maintainers = with maintainers; [ sb0 ];
    platforms = platforms.linux;
  };
}
