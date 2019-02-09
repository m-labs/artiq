let 
  pkgs = import <nixpkgs> {};
  fetchcargo = import <nixpkgs/pkgs/build-support/rust/fetchcargo.nix> {
    inherit (pkgs) stdenv cacert git rust cargo-vendor;
  };
  myVendoredSrcFetchCargo = fetchcargo rec {
    name = "myVendoredSrcFetchCargo";
    sourceRoot = null;
    srcs = null;
    src = ../artiq/firmware;
    cargoUpdateHook = "";
    patches = [];
    sha256 = "1xzjn9i4rkd9124v2gbdplsgsvp1hlx7czdgc58n316vsnrkbr86";
  };

  myVendoredSrc = pkgs.stdenv.mkDerivation {
    name = "myVendoredSrc";
    src = myVendoredSrcFetchCargo;
    phases = [ "unpackPhase" "installPhase" ];
    installPhase = ''
      mkdir -p $out/.cargo/registry
      cat > $out/.cargo/config << EOF
        [source.crates-io]
        registry = "https://github.com/rust-lang/crates.io-index"
        replace-with = "vendored-sources"

        [source."https://github.com/m-labs/libfringe"]
        git = "https://github.com/m-labs/libfringe"
        rev = "b8a6d8f"
        replace-with = "vendored-sources"

        [source.vendored-sources]
        directory = "$out/.cargo/registry"
      EOF
      cp -R * $out/.cargo/registry
    '';
  };

  buildenv = import ./artiq-dev.nix { inherit pkgs; };

in pkgs.stdenv.mkDerivation {
  name = "artiq-board";
  src = null;
  phases = [ "buildPhase" "installPhase" ];
  buildPhase = 
    ''
    ${buildenv}/bin/artiq-dev -c "HOME=${myVendoredSrc} python -m artiq.gateware.targets.kasli -V satellite --no-compile-gateware"
    '';
  installPhase =
    ''
    mkdir $out
    #cp artiq_kasli/satellite/gateware/top.bit $out
    cp artiq_kasli/satellite/software/bootloader/bootloader.bin $out
    cp artiq_kasli/satellite/software/satman/satman.{elf,fbi} $out
    '';
}
