{system ? builtins.currentSystem}:
let
  pkgs = import <nixpkgs> {inherit system;};
  callPackage = pkgs.lib.callPackageWith (pkgs // self );

self = {
  binutils-or1k = callPackage ./binutils-or1k.nix {};
  llvm-src = callPackage ./fetch-llvm-clang.nix {};
  llvm-or1k = callPackage ./llvm-or1k.nix {};
  llvmlite = callPackage ./llvmlite.nix {};
  artiq = callPackage ./artiq.nix { };
};
artiq = self.artiq;
in
artiq
