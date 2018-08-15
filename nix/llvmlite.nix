{ stdenv, fetchgit, llvm-or1k, makeWrapper, python35, ncurses, zlib, python35Packages }:
let
version = "0f4ebae";
in
stdenv.mkDerivation rec {
  name = "llvmlite-${version}";
  src = fetchgit {
    url = "https://github.com/m-labs/llvmlite";
    rev = "401dfb713166bdd2bc0d3ab2b7ebf12e7a434130";
    sha256 = "1ci1pnpspv1pqz712yix1nmplq7568vpsr6gzzl3a33w9s0sw2nq";
    leaveDotGit = true;
  };

  buildInputs = [ makeWrapper python35 ncurses zlib llvm-or1k python35Packages.setuptools ];

  installPhase = ''
    LLVM_CONFIG=${llvm-or1k}/bin/llvm-config
    python3 setup.py install --prefix=$out
  '';
}
