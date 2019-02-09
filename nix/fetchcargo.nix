{ stdenv, cacert, git, cargo, cargo-vendor }:
{ name, src, sha256 }:
stdenv.mkDerivation {
  name = "${name}-vendor";
  nativeBuildInputs = [ cacert git cargo cargo-vendor ];
  inherit src;

  phases = "unpackPhase patchPhase installPhase";

  installPhase = ''
    if [[ ! -f Cargo.lock ]]; then
        echo
        echo "ERROR: The Cargo.lock file doesn't exist"
        echo
        echo "Cargo.lock is needed to make sure that cargoSha256 doesn't change"
        echo "when the registry is updated."
        echo

        exit 1
    fi

    export CARGO_HOME=$(mktemp -d cargo-home.XXX)

    cargo vendor

    cp -ar vendor $out
  '';

  outputHashAlgo = "sha256";
  outputHashMode = "recursive";
  outputHash = sha256;

  impureEnvVars = stdenv.lib.fetchers.proxyImpureEnvVars;
  preferLocalBuild = true;
}
