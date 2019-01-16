{ stdenv, buildPackages
, fetchurl, zlib
}:

stdenv.mkDerivation rec {
  basename = "binutils";
  platform = "or1k";
  version = "2.30";
  name = "${basename}_${platform}-${version}";
  src = fetchurl {
    url = "https://ftp.gnu.org/gnu/binutils/binutils-${version}.tar.bz2";
    sha256 = "028cklfqaab24glva1ks2aqa1zxa6w6xmc8q34zs1sb7h22dxspg";
  };
  configureFlags =
    [ "--enable-shared" "--enable-deterministic-archives" "--target=or1k-linux"];
  outputs = [ "out" "info" "man" ];
  depsBuildBuild = [ buildPackages.stdenv.cc ];
  buildInputs = [ zlib ];
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
