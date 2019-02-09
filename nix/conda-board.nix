{ pkgs ? import <nixpkgs> {}}:
{ artiqSrc, boardBinaries }:

with pkgs;

let
  target = "kasli";
  variant = "tester";

  fakeCondaSource = runCommand "fake-conda-source-${target}-${variant}" { }
    ''
    cp --no-preserve=mode,ownership -R ${artiqSrc} $out
    mkdir $out/fake-conda;

    cat << EOF > $out/fake-conda/meta.yaml
    package:
      name: artiq-${target}-${variant}
      version: {{ environ["GIT_DESCRIBE_TAG"] }}

    source:
      git_url: ..

    build:
      noarch: python
      number: {{ environ["GIT_DESCRIBE_NUMBER"] }}
      string: {{ environ["GIT_DESCRIBE_NUMBER"] }}+git{{ environ["GIT_FULL_HASH"][:8] }}
      ignore_prefix_files: True

    outputs:
      - name: artiq-${target}-${variant}
        noarch: python
        files:
          - site-packages
        requirements:
          run:
            - artiq {{ "{tag} {number}+git{hash}".format(tag=environ["GIT_DESCRIBE_TAG"], number=environ["GIT_DESCRIBE_NUMBER"], hash=environ["GIT_FULL_HASH"][:8]) }}
        ignore_prefix_files: True

    about:
      home: https://m-labs.hk/artiq
      license: LGPL
      summary: 'Bitstream, BIOS and firmware for the ${target}-${variant} board variant'
    EOF

    cat << EOF > $out/fake-conda/build.sh
    #!/bin/bash
    set -e
    SOC_PREFIX=\$PREFIX/site-packages/artiq/binaries/${target}-${variant}
    mkdir -p \$SOC_PREFIX
    cp ${boardBinaries}/* \$SOC_PREFIX
    EOF
    chmod 755 $out/fake-conda/build.sh
    '';
  conda-board = import ./conda-build.nix { inherit pkgs; } {
    name = "conda-board-${target}-${variant}";
    src = fakeCondaSource;
    recipe = "fake-conda";
  };
in
  conda-board
