{system ? builtins.currentSystem}:
let
  pkgs = import <nixpkgs> {inherit system;};
  artiq = pkgs.callPackage ./default.nix {};
in
pkgs.mkShell {
  buildInputs = [ artiq ];
}
