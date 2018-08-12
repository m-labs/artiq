{ stdenv, fetchgit, llvm-or1k, makeWrapper, python35, ncurses, zlib, python35Packages }:
let
version = "0f4ebae";
in
stdenv.mkDerivation rec {
  name = "llvmlite-${version}";
  src = fetchgit {
    url = "https://github.com/m-labs/llvmlite";
    rev = "0f4ebae43c2d2a084deb8b693e3d42a7b2c82222";
    sha256 = "0n90w0x001k0zyn8zz6jxc9i78agqv15m55vz2raw1y0rfw16mfl";
    leaveDotGit = true;
  };

  buildInputs = [ makeWrapper python35 ncurses zlib llvm-or1k python35Packages.setuptools ];

  installPhase = ''
    LLVM_CONFIG=${llvm-or1k}/llvm_or1k/bin/llvm-config
    python3 setup.py install --prefix=$out
  '';
}
