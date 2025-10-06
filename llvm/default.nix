{
  lib,
  stdenv,
  callPackage,
  fetchFromGitHub,
  cmake,
  ninja,
  python3,
  libffi,
  libxml2,
  ncurses,
  zlib,
  runCommand,
}: let
  version = "15.0.7";

  src = fetchFromGitHub {
    owner = "llvm";
    repo = "llvm-project";
    rev = "llvmorg-${version}";
    sha256 = "sha256-wjuZQyXQ/jsmvy6y1aksCcEDXGBjuhpgngF3XQJ/T4s=";
  };

  llvm_meta = {
    license = lib.licenses.ncsa;
    platforms = lib.platforms.unix;
  };

  getVersionFile = p: ./15 + "/${p}";

  # Build LLVM first (provides libllvm and llvm-tblgen)
  libllvm = callPackage ./15/llvm {
    inherit
      lib
      stdenv
      cmake
      ninja
      python3
      libffi
      libxml2
      ncurses
      zlib
      runCommand
      src
      version
      llvm_meta
      getVersionFile
      ;
  };

  clang-unwrapped = callPackage ./15/clang {
    inherit
      lib
      stdenv
      cmake
      ninja
      python3
      libxml2
      runCommand
      libllvm
      src
      version
      llvm_meta
      getVersionFile
      ;
  };

  lld = callPackage ./15/lld {
    inherit
      lib
      stdenv
      cmake
      ninja
      libxml2
      libllvm
      runCommand
      src
      version
      llvm_meta
      getVersionFile
      ;
  };
in {
  llvm_15 = libllvm;
  lld_15 = lld;
  llvmPackages_15 = {clang-unwrapped = clang-unwrapped;};
}
