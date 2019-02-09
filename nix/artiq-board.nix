{ pkgs ? import <nixpkgs> {}}:

let
  artiqPkgs = import ./default.nix { inherit pkgs; };
  fetchcargo = import ./fetchcargo.nix {
    inherit (pkgs) stdenv cacert git cargo cargo-vendor;
  };
  cargoDeps = fetchcargo rec {
    name = "artiq-firmware-cargo-deps";
    src = ../artiq/firmware;
    sha256 = "1xzjn9i4rkd9124v2gbdplsgsvp1hlx7czdgc58n316vsnrkbr86";
  };

  cargoVendored = pkgs.stdenv.mkDerivation {
    name = "artiq-firmware-cargo-vendored";
    src = cargoDeps;
    phases = [ "unpackPhase" "installPhase" ];
    installPhase =
      ''
      mkdir -p $out/registry
      cat > $out/config <<-EOF
        [source.crates-io]
        registry = "https://github.com/rust-lang/crates.io-index"
        replace-with = "vendored-sources"

        [source."https://github.com/m-labs/libfringe"]
        git = "https://github.com/m-labs/libfringe"
        rev = "b8a6d8f"
        replace-with = "vendored-sources"

        [source.vendored-sources]
        directory = "$out/registry"
      EOF
      cp -R * $out/registry
      '';
  };

  buildenv = import ./artiq-dev.nix { inherit pkgs; };

in pkgs.stdenv.mkDerivation {
  name = "artiq-board";
  src = null;
  phases = [ "buildPhase" "installPhase" ];
  buildPhase = 
    ''
    ${buildenv}/bin/artiq-dev -c "CARGO_HOME=${cargoVendored} python -m artiq.gateware.targets.kasli -V tester --no-compile-gateware"
    '';
  installPhase =
    ''
    mkdir $out
    #cp artiq_kasli/tester/gateware/top.bit $out
    cp artiq_kasli/tester/software/bootloader/bootloader.bin $out
    cp artiq_kasli/tester/software/runtime/runtime.{elf,fbi} $out
    '';
}
