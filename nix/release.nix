{ pkgs ? import <nixpkgs> {}}:
let
  artiqPkgs = import ./default.nix { inherit pkgs; };
  artiq-board = import ./artiq-board.nix { inherit pkgs; };
  jobs = rec {
    conda-artiq = import ./conda-build.nix { inherit pkgs; } {
      name = "conda-artiq";
      src = ../.;
      recipe = "conda/artiq";
    };
    inherit artiq-board;
    conda-artiq-board = import ./conda-board.nix { inherit pkgs; } {
      artiqSrc = ../.;
      boardBinaries = artiq-board;
    };
  } // artiqPkgs;
in
  jobs
