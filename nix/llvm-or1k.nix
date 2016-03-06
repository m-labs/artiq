{ stdenv
, git
, llvm-src
,  perl, groff, cmake, libxml2, python, libffi, valgrind
, ...
}:

stdenv.mkDerivation rec {
  name = "llvm_or1k";
  src = llvm-src;

 buildInputs = [ perl groff cmake libxml2 python libffi ] ++ stdenv.lib.optional stdenv.isLinux valgrind;

  preBuild = ''
    NIX_BUILD_CORES=4
    makeFlagsArray=(-j''$NIX_BUILD_CORES)
    mkdir -p $out/
  '';

  cmakeFlags = with stdenv; [
    "-DLLVM_TARGETS_TO_BUILD=OR1K;X86"
    "-DCMAKE_BUILD_TYPE=Rel"
    "-DLLVM_ENABLE_ASSERTIONS=ON"
    "-DCMAKE_BUILD_TYPE=Release"
  ];

  enableParallelBuilding = true;
  meta = {
    description = "Collection of modular and reusable compiler and toolchain technologies";
    homepage = http://llvm.org/;
    license = stdenv.lib.licenses.bsd3;
    maintainers = with stdenv.lib.maintainers; [ sj_mackenzie ];
    platforms = stdenv.lib.platforms.all;
  };
}

