{ stdenv, callPackage, recurseIntoAttrs, makeRustPlatform, llvm, fetchurl
, targets ? []
, targetToolchains ? []
, targetPatches ? []
, fetchFromGitHub
}:

let
  rustPlatform = recurseIntoAttrs (makeRustPlatform (callPackage ./bootstrap.nix {}));
  version = "1.28.0";
  cargoVersion = "1.28.0";
  src = fetchFromGitHub {
    owner = "m-labs";
    repo = "rust";
    sha256 = "03lfps3xvvv7wv1nnwn3n1ji13z099vx8c3fpbzp9rnasrwzp5jy";
    rev = "f305fb024318e96997fbe6e4a105b0cc1052aad4"; #  artiq-1.28.0 branch
    fetchSubmodules = true;
  };
in rec {
  # nixcloud team code
  or1k-crates = stdenv.mkDerivation {
    name = "or1k-crates";
    inherit src;
    phases = [ "unpackPhase" "buildPhase" ];
    buildPhase = ''
      destdir=$out
      rustc="${rustc_internal}/bin/rustc --out-dir ''${destdir} -L ''${destdir} --target or1k-unknown-none -g -C target-feature=+mul,+div,+ffl1,+cmov,+addc -C opt-level=s --crate-type rlib"
      
      mkdir -p ''${destdir}
      ''${rustc} --crate-name core src/libcore/lib.rs
      ''${rustc} --crate-name compiler_builtins src/libcompiler_builtins/src/lib.rs --cfg 'feature="compiler-builtins"' --cfg 'feature="mem"'
      ''${rustc} --crate-name std_unicode src/libstd_unicode/lib.rs
      ''${rustc} --crate-name alloc src/liballoc/lib.rs
      ''${rustc} --crate-name libc src/liblibc_mini/lib.rs
      ''${rustc} --crate-name unwind src/libunwind/lib.rs
      ''${rustc} -Cpanic=abort --crate-name panic_abort src/libpanic_abort/lib.rs
      ''${rustc} -Cpanic=unwind --crate-name panic_unwind src/libpanic_unwind/lib.rs --cfg llvm_libunwind
    '';
  };
  # nixcloud team code
  # this is basically a wrapper, which uses rustc_internal and inserts or1k-crates into it
  rustc = stdenv.mkDerivation {
    name = "rustc";
    src = ./.;
    installPhase = ''
      mkdir $out
      mkdir -p $out/lib/rustlib/or1k-unknown-none/lib/
      cp -r ${or1k-crates}/* $out/lib/rustlib/or1k-unknown-none/lib/
      cp -r ${rustc_internal}/* $out
    '';
  };
  # nixcloud team code
  # originally rustc but now renamed to rustc_internal
  rustc_internal = callPackage ./rustc.nix {
    inherit stdenv llvm targets targetPatches targetToolchains rustPlatform version src;

    patches = [
      ./patches/net-tcp-disable-tests.patch

      # Re-evaluate if this we need to disable this one
      #./patches/stdsimd-disable-doctest.patch

      # Fails on hydra - not locally; the exact reason is unknown.
      # Comments in the test suggest that some non-reproducible environment
      # variables such $RANDOM can make it fail.
      ./patches/disable-test-inherit-env.patch
    ];

    forceBundledLLVM = true;

    #configureFlags = [ "--release-channel=stable" ];

    # 1. Upstream is not running tests on aarch64:
    # see https://github.com/rust-lang/rust/issues/49807#issuecomment-380860567
    # So we do the same.
    # 2. Tests run out of memory for i686
    #doCheck = !stdenv.isAarch64 && !stdenv.isi686;

    # Disabled for now; see https://github.com/NixOS/nixpkgs/pull/42348#issuecomment-402115598.
    doCheck = false;
  };

  cargo = callPackage ./cargo.nix rec {
    version = cargoVersion;
    inherit src;
    inherit stdenv;
    inherit rustc; # the rustc that will be wrapped by cargo
    inherit rustPlatform; # used to build cargo
  };
}
