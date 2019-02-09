{ pkgs ? import <nixpkgs> {}}:
let
  artiqPkgs = import ./default.nix { inherit pkgs; };
  jobs = rec {
    conda-artiq = import ./conda-build.nix { inherit pkgs; };
  } // artiqPkgs;
in
  jobs
