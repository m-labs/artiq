{
  lib,
  stdenv,
  cmake,
  ninja,
  python3,
  libxml2,
  runCommand,
  libllvm,
  src,
  version,
  llvm_meta,
  getVersionFile,
}:
stdenv.mkDerivation {
  pname = "clang";
  inherit version;

  # Extract clang from monorepo
  src = runCommand "clang-src-${version}" {} ''
    mkdir -p "$out"
    cp -r ${src}/cmake "$out"
    cp -r ${src}/clang "$out"
    cp -r ${src}/clang-tools-extra "$out"
  '';

  sourceRoot = "clang-src-${version}/clang";

  outputs = [
    "out"
    "lib"
    "dev"
    "python"
  ];

  patches = [
    (getVersionFile "clang/purity.patch")
    (getVersionFile "clang/gnu-install-dirs.patch")
  ];

  nativeBuildInputs = [
    cmake
    ninja
    python3
  ];
  buildInputs = [
    libxml2
    libllvm
  ];

  cmakeFlags = [
    "-DLLVM_ENABLE_RTTI=ON"
    "-DCLANG_INSTALL_PACKAGE_DIR=${placeholder "dev"}/lib/cmake/clang"
    "-DLLVM_TABLEGEN_EXE=${libllvm.dev}/bin/llvm-tblgen"
  ];

  postPatch = ''
    # Link clang-tools-extra
    (cd tools && ln -s ../../clang-tools-extra extra)
  '';

  postInstall = ''
    # Create cpp symlink
    ln -sv $out/bin/clang $out/bin/cpp

    # Move libclang to lib output
    moveToOutput "lib/libclang.*" "$lib"
    moveToOutput "lib/libclang-cpp.*" "$lib"

    # Setup python output
    mkdir -p $python/bin $python/share/clang/
    mv $out/bin/{git-clang-format,scan-view} $python/bin
    if [ -e $out/bin/set-xcode-analyzer ]; then
      mv $out/bin/set-xcode-analyzer $python/bin
    fi
    mv $out/share/clang/*.py $python/share/clang

    # Remove test binary
    rm $out/bin/c-index-test

    # Move tblgen to dev
    mkdir -p $dev/bin
    cp bin/clang-tblgen $dev/bin
  '';

  passthru = {
    inherit libllvm;
    isClang = true;
  };

  meta =
    llvm_meta
    // {
      description = "C language family frontend for LLVM";
      homepage = "https://clang.llvm.org/";
    };
}
