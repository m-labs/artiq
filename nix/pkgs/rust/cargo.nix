{ stdenv, fetchurl, file, curl, pkgconfig, python, openssl, cmake, zlib
, makeWrapper, libiconv, cacert, rustPlatform, rustc, libgit2, darwin
, version
, patches ? []
, src }:

let
  inherit (darwin.apple_sdk.frameworks) CoreFoundation;
  src_rustc = fetchurl {
    url = "https://static.rust-lang.org/dist/rustc-1.28.0-src.tar.gz";
    sha256 = "11k4rn77bca2rikykkk9fmprrgjswd4x4kaq7fia08vgkir82nhx";
  };
in

rustPlatform.buildRustPackage rec {
  name = "cargo-${version}";
  inherit version src patches;

  # the rust source tarball already has all the dependencies vendored, no need to fetch them again
  cargoVendorDir = "src/vendor";
  preBuild = "cd src; pushd tools/cargo";
  postBuild = "popd";

  passthru.rustc = rustc;

  # changes hash of vendor directory otherwise
  dontUpdateAutotoolsGnuConfigScripts = true;

  nativeBuildInputs = [ pkgconfig ];
  buildInputs = [ cacert file curl python openssl cmake zlib makeWrapper libgit2 ]
    ++ stdenv.lib.optionals stdenv.isDarwin [ CoreFoundation libiconv ];

  LIBGIT2_SYS_USE_PKG_CONFIG=1;

  # fixes: the cargo feature `edition` requires a nightly version of Cargo, but this is the `stable` channel
  RUSTC_BOOTSTRAP=1;

  preConfigure = ''
        tar xf ${src_rustc}
    mv rustc-1.28.0-src/src/vendor/ src/vendor
  '';

  postInstall = ''
    # NOTE: We override the `http.cainfo` option usually specified in
    # `.cargo/config`. This is an issue when users want to specify
    # their own certificate chain as environment variables take
    # precedence
    wrapProgram "$out/bin/cargo" \
      --suffix PATH : "${rustc}/bin" \
      --set CARGO_HTTP_CAINFO "${cacert}/etc/ssl/certs/ca-bundle.crt" \
      --set SSL_CERT_FILE "${cacert}/etc/ssl/certs/ca-bundle.crt"
  '';

  checkPhase = ''
    # Disable cross compilation tests
    export CFG_DISABLE_CROSS_TESTS=1
    cargo test
  '';

  # Disable check phase as there are failures (4 tests fail)
  doCheck = false;

  meta = with stdenv.lib; {
    homepage = https://crates.io;
    description = "Downloads your Rust project's dependencies and builds your project";
    maintainers = with maintainers; [ sb0 ];
    license = [ licenses.mit licenses.asl20 ];
    platforms = platforms.unix;
  };
}
