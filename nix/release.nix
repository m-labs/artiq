{ pkgs ? import <nixpkgs> {}}:
with pkgs;
let
  artiqPkgs = import ./default.nix {};
  jobs = rec {
    conda-artiq = callPackage ./conda-build.nix {};
  } // artiqPkgs;
in
  jobs
