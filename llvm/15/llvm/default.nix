{
  lib,
  stdenv,
  cmake,
  ninja,
  python3,
  libffi,
  libxml2,
  ncurses,
  zlib,
  runCommand,
  src,
  version,
  llvm_meta,
  getVersionFile,
}:
stdenv.mkDerivation {
  pname = "llvm";
  inherit version;

  src = runCommand "llvm-src-${version}" {} ''
    mkdir -p "$out"
    cp -r ${src}/llvm "$out"
    cp -r ${src}/cmake "$out"
    cp -r ${src}/third-party "$out"
  '';

  sourceRoot = "llvm-src-${version}/llvm";

  outputs = ["out" "lib" "dev" "python"];

  patches = [
    (getVersionFile "llvm/gnu-install-dirs.patch")
    (getVersionFile "llvm/llvm-lit-cfg-add-libs-to-dylib-path.patch")
    (getVersionFile "llvm/lit-shell-script-runner-set-dyld-library-path.patch")
  ];

  nativeBuildInputs = [cmake ninja python3];
  buildInputs = [libxml2 libffi];
  propagatedBuildInputs = [ncurses zlib];

  cmakeBuildType = "Release";

  cmakeFlags = [
    "-DLLVM_INSTALL_PACKAGE_DIR=${placeholder "dev"}/lib/cmake/llvm"
    "-DLLVM_ENABLE_RTTI=ON"
    "-DLLVM_LINK_LLVM_DYLIB=ON"
    "-DLLVM_INSTALL_UTILS=ON"
    "-DLLVM_BUILD_TESTS=OFF"
    "-DLLVM_ENABLE_FFI=ON"
    "-DLLVM_HOST_TRIPLE=${stdenv.hostPlatform.config}"
    "-DLLVM_DEFAULT_TARGET_TRIPLE=${stdenv.hostPlatform.config}"
    "-DLLVM_ENABLE_DUMP=ON"
    "-DLLVM_ENABLE_TERMINFO=ON"
    "-DLLVM_INCLUDE_TESTS=OFF"
  ];

  LDFLAGS = "-Wl,--build-id=sha1";

  postInstall = ''
    # Move opt-viewer to python output
    mkdir -p $python/share
    mv $out/share/opt-viewer $python/share/opt-viewer

    # Move llvm-config to dev output
    moveToOutput "bin/llvm-config*" "$dev"

    # Move llvm-tblgen to dev output (needed by clang and lld)
    moveToOutput "bin/llvm-tblgen" "$dev"

    # Fix cmake config to point to dev output
    substituteInPlace "$dev/lib/cmake/llvm/LLVMExports-release.cmake" \
      --replace-fail "$out/bin/llvm-config" "$dev/bin/llvm-config" \
      --replace-fail "$out/bin/llvm-tblgen" "$dev/bin/llvm-tblgen"

    substituteInPlace "$dev/lib/cmake/llvm/LLVMConfig.cmake" \
      --replace-fail 'set(LLVM_BINARY_DIR "''${LLVM_INSTALL_PREFIX}")' 'set(LLVM_BINARY_DIR "'"$lib"'")'
  '';

  meta =
    llvm_meta
    // {
      description = "LLVM compiler infrastructure";
      homepage = "https://llvm.org/";
    };
}
