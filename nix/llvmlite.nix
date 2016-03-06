{ stdenv, fetchgit, llvm-or1k, makeWrapper, python35, ncurses, zlib }:
let
version = "0f4ebae";
in
stdenv.mkDerivation rec {
  name = "llvmlite-${version}";
  src = fetchgit {
    url = "https://github.com/m-labs/llvmlite";
    rev = "0f4ebae43c2d2a084deb8b693e3d42a7b2c82222";
    sha256 = "0lnxxyjw2dapzqanms6jx64zxwhyrcria1yz49dzlb1306hzclj0";
    leaveDotGit = true;
  };

  buildInputs = [ makeWrapper python35 ncurses zlib llvm-or1k];

  installPhase = ''
    LLVM_CONFIG=${llvm-or1k}/llvm_or1k/bin/llvm-config
    python3 setup.py install --prefix=$out
  '';
}
