{ pkgs ? import <nixpkgs> {}}:
let
  artiqPkgs = import ./default.nix { inherit pkgs; };
  jobs = rec {
    conda-artiq = import ./conda-build.nix { inherit pkgs; } {
      name = "conda-artiq";
      src = ../.;
      recipe = "conda/artiq";
    };
    artiq-board-kasli-tester = import ./artiq-board.nix { inherit pkgs; } {
      target = "kasli";
      variant = "tester";
    };
    conda-artiq-board-kasli-tester = import ./conda-board.nix { inherit pkgs; } {
      artiqSrc = ../.;
      boardBinaries = artiq-board-kasli-tester;
      target = "kasli";
      variant = "tester";
    };
  } // artiqPkgs;
in
  jobs
