{ stdenv
, fetchurl
}:

stdenv.mkDerivation rec {
  basename = "binutils";
  platform = "or1k";
  version = "2.26";
  name = "${basename}_${platform}-${version}";
  src = fetchurl {
    url = "https://ftp.gnu.org/gnu/binutils/${basename}-${version}.tar.bz2";
    sha256 = "1ngc2h3knhiw8s22l8y6afycfaxr5grviqy7mwvm4bsl14cf9b62";
  };
  configureFlags =
    [ "--enable-shared" "--enable-deterministic-archives" "--target=or1k-linux"];
  enableParallelBuilding = true;
  meta = {
    description = "Tools for manipulating binaries (linker, assembler, etc.)";
    longDescription = ''
      The GNU Binutils are a collection of binary tools.  The main
      ones are `ld' (the GNU linker) and `as' (the GNU assembler).
      They also include the BFD (Binary File Descriptor) library,
      `gprof', `nm', `strip', etc.
    '';
    homepage = http://www.gnu.org/software/binutils/;
    license = stdenv.lib.licenses.gpl3Plus;
    /* Give binutils a lower priority than gcc-wrapper to prevent a
       collision due to the ld/as wrappers/symlinks in the latter. */
    priority = "10";
  };
}

