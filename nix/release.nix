{ pkgs ? import <nixpkgs> {}}:
let
  artiqPkgs = import ./default.nix { inherit pkgs; };

  boards = [
    {
      target = "kasli";
      variant = "tester";
    }
    {
      target = "kc705";
      variant = "nist_clock";
    }
  ];
  boardJobs = pkgs.lib.lists.foldr (board: start:
    let
      boardBinaries = import ./artiq-board.nix { inherit pkgs; } {
        target = board.target;
        variant = board.variant;
      };
    in
      start // {
        "artiq-board-${board.target}-${board.variant}" = boardBinaries;
        "conda-artiq-board-${board.target}-${board.variant}" = import ./conda-board.nix { inherit pkgs; } {
          artiqSrc = ../.;
          boardBinaries = boardBinaries;
          target = board.target;
          variant = board.variant;
      };
  }) {} boards;

  jobs = {
    conda-artiq = import ./conda-build.nix { inherit pkgs; } {
      name = "conda-artiq";
      src = ../.;
      recipe = "conda/artiq";
    };
  } // boardJobs // artiqPkgs;
in
  jobs // {
    channel = pkgs.releaseTools.channel {
      name = "main";
      src = ./.;
      constitutents = builtins.attrValues jobs;
    };
  }
