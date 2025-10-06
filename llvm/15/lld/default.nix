{
  lib,
  stdenv,
  cmake,
  ninja,
  libxml2,
  libllvm,
  runCommand,
  src,
  version,
  llvm_meta,
  getVersionFile,
}:
stdenv.mkDerivation {
  pname = "lld";
  inherit version;

  src = runCommand "lld-src-${version}" {} ''
    mkdir -p "$out"
    cp -r ${src}/cmake "$out"
    cp -r ${src}/lld "$out"
    mkdir -p "$out/libunwind"
    cp -r ${src}/libunwind/include "$out/libunwind"
    mkdir -p "$out/llvm"
  '';

  sourceRoot = "lld-src-${version}/lld";

  outputs = ["out" "lib" "dev"];

  patches = [
    (getVersionFile "lld/gnu-install-dirs.patch")
  ];

  nativeBuildInputs = [cmake ninja];
  buildInputs = [libllvm libxml2];

  cmakeFlags = [
    "-DLLD_INSTALL_PACKAGE_DIR=${placeholder "dev"}/lib/cmake/lld"
    "-DLLVM_TABLEGEN_EXE=${libllvm.dev}/bin/llvm-tblgen"
  ];

  meta =
    llvm_meta
    // {
      description = "LLVM linker";
      homepage = "https://lld.llvm.org/";
    };
}
