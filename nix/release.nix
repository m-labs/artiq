{ pkgs ? import <nixpkgs> {}}:
let
  artiqPkgs = import ./default.nix { inherit pkgs; };
  jobs = rec {
    conda-artiq = import ./conda-build.nix { inherit pkgs; };
    artiq-board = import ./artiq-board.nix { inherit pkgs; };
  } // artiqPkgs;
in
  jobs
