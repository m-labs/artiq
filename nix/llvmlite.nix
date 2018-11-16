{ stdenv, fetchFromGitHub, llvm-or1k, makeWrapper, python3, ncurses, zlib, python3Packages }:
let
version = "0f4ebae";
in
stdenv.mkDerivation rec {
  name = "llvmlite-${version}";
  src = fetchFromGitHub {
    rev = "401dfb713166bdd2bc0d3ab2b7ebf12e7a434130";
    owner = "m-labs";
    repo = "llvmlite";
    sha256 = "1hqahd87ihwgjsaxv0y2iywldi1zgyjxjfy3sy3rr1gnwvxb47xw";
  };

  buildInputs = [ makeWrapper python3 ncurses zlib llvm-or1k python3Packages.setuptools ];

  installPhase = ''
    LLVM_CONFIG=${llvm-or1k}/bin/llvm-config
    python3 setup.py install --prefix=$out
  '';
}
