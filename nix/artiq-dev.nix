{ pkgs ? import <nixpkgs> {}}:

let 
  artiqpkgs = import ./default.nix { inherit pkgs; };
in
  pkgs.buildFHSUserEnv {
    name = "artiq-dev";
    targetPkgs = pkgs: (
      with pkgs; [
        ncurses5
        gnumake
        zlib
        libuuid
        xorg.libSM
        xorg.libICE
        xorg.libXrender
        xorg.libX11
        xorg.libXext
        xorg.libXtst
        xorg.libXi
        (python3.withPackages(ps: with ps; [ jinja2 numpy artiqpkgs.migen artiqpkgs.microscope artiqpkgs.misoc artiqpkgs.jesd204b artiqpkgs.artiq ]))
        git
      ] ++
      (with artiqpkgs; [
        rustc
        cargo
        binutils-or1k
        llvm-or1k
        openocd
      ])
    );
    profile = ''
      export TARGET_AR=${artiqpkgs.binutils-or1k}/bin/or1k-linux-ar
    '';
  }
