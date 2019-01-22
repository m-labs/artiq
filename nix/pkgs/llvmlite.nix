{ stdenv, fetchFromGitHub, llvm-or1k, makeWrapper, python3, ncurses, zlib, python3Packages }:
stdenv.mkDerivation rec {
  name = "llvmlite";
  src = fetchFromGitHub {
    rev = "1d167be4eec5d6c32498952be8b3ac17dd30df8d";
    owner = "m-labs";
    repo = "llvmlite";
    sha256 = "0ranbjhcz2v3crmdbw1sxdwqwqbbm7dd53d8qaqb69ma9fkxy8x7";
  };

  buildInputs = [ makeWrapper python3 ncurses zlib llvm-or1k python3Packages.setuptools ];

  installPhase = ''
    LLVM_CONFIG=${llvm-or1k}/bin/llvm-config
    python3 setup.py install --prefix=$out
  '';

  meta = with stdenv.lib; {
      description = "A lightweight LLVM python binding for writing JIT compilers";
      homepage    = "http://llvmlite.pydata.org/";
      #maintainers = with maintainers; [ sb0 ];
      license     = licenses.bsd2;
      platforms   = platforms.unix;
  };
}
