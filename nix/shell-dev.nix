{ pkgs ? import <nixpkgs> {}}:

let
  artiq-dev = import ./artiq-dev.nix { inherit pkgs; };
in
  artiq-dev.env
