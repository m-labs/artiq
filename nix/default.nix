{ pkgs ? import <nixpkgs> {}}:
with pkgs;
let
  # this code was copied from nipxkgs rev. ffafe9 (nixcloud team) and slightly modified
  rust = callPackage ./pkgs/rust
    (stdenv.lib.optionalAttrs (stdenv.cc.isGNU && stdenv.hostPlatform.isi686) {
      stdenv = overrideCC stdenv gcc6; # with gcc-7: undefined reference to `__divmoddi4'
    });
  llvm-src = callPackage ./fetch-llvm-clang.nix {};
in rec {
  inherit (rust) rustc;
  inherit (callPackage ./pkgs/python3Packages.nix {}) migen microscope misoc jesd204b;
  binutils-or1k = callPackage ./pkgs/binutils-or1k.nix {};
  llvm-or1k = callPackage ./pkgs/llvm-or1k.nix { inherit llvm-src; };
  llvmlite = callPackage ./pkgs/llvmlite.nix { inherit llvm-or1k; };
  artiq = callPackage ./pkgs/artiq.nix { inherit binutils-or1k; inherit llvm-or1k; inherit llvmlite; };
  openocd = callPackage ./pkgs/openocd.nix {};
}
