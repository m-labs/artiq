{
  description = "A leading-edge control system for quantum information experiments";

  inputs.nixpkgs.url = github:NixOS/nixpkgs/nixos-22.05;
  inputs.mozilla-overlay = { url = github:mozilla/nixpkgs-mozilla; flake = false; };
  inputs.sipyco.url = github:m-labs/sipyco;
  inputs.sipyco.inputs.nixpkgs.follows = "nixpkgs";
  inputs.src-pythonparser = { url = github:m-labs/pythonparser; flake = false; };
  inputs.artiq-comtools.url = github:m-labs/artiq-comtools;
  inputs.artiq-comtools.inputs.nixpkgs.follows = "nixpkgs";
  inputs.artiq-comtools.inputs.sipyco.follows = "sipyco";

  inputs.src-migen = { url = github:m-labs/migen; flake = false; };
  inputs.src-misoc = { type = "git"; url = "https://github.com/m-labs/misoc.git"; submodules = true; flake = false; };

  outputs = { self, nixpkgs, mozilla-overlay, sipyco, src-pythonparser, artiq-comtools, src-migen, src-misoc }:
    let
      pkgs = import nixpkgs { system = "x86_64-linux"; overlays = [ (import mozilla-overlay) ]; };
      pkgs-aarch64 = import nixpkgs { system = "aarch64-linux"; };

      artiqVersionMajor = 8;
      artiqVersionMinor = self.sourceInfo.revCount or 0;
      artiqVersionId = self.sourceInfo.shortRev or "unknown";
      artiqVersion = (builtins.toString artiqVersionMajor) + "." + (builtins.toString artiqVersionMinor) + "." + artiqVersionId + ".beta";
      artiqRev = self.sourceInfo.rev or "unknown";

      rustManifest = pkgs.fetchurl {
        url = "https://static.rust-lang.org/dist/2021-01-29/channel-rust-nightly.toml";
        sha256 = "sha256-EZKgw89AH4vxaJpUHmIMzMW/80wAFQlfcxRoBD9nz0c=";
      };

      targets = [];
      rustChannelOfTargets = _channel: _date: targets:
        (pkgs.lib.rustLib.fromManifestFile rustManifest {
          inherit (pkgs) stdenv lib fetchurl patchelf;
        }).rust.override {
          inherit targets;
          extensions = ["rust-src"];
        };
      rust = rustChannelOfTargets "nightly" null targets;
      rustPlatform = pkgs.recurseIntoAttrs (pkgs.makeRustPlatform {
        rustc = rust;
        cargo = rust;
      });

      vivadoDeps = pkgs: with pkgs; [
        ncurses5
        zlib
        libuuid
        xorg.libSM
        xorg.libICE
        xorg.libXrender
        xorg.libX11
        xorg.libXext
        xorg.libXtst
        xorg.libXi
        freetype
        fontconfig
      ];

      pythonparser = pkgs.python3Packages.buildPythonPackage {
        pname = "pythonparser";
        version = "1.4";
        src = src-pythonparser;
        doCheck = false;
        propagatedBuildInputs = with pkgs.python3Packages; [ regex ];
      };

      qasync = pkgs.python3Packages.buildPythonPackage rec {
        pname = "qasync";
        version = "0.19.0";
        src = pkgs.fetchFromGitHub {
          owner = "CabbageDevelopment";
          repo = "qasync";
          rev = "v${version}";
          sha256 = "sha256-xGAUAyOq+ELwzMGbLLmXijxLG8pv4a6tPvfAVOt1YwU=";
        };
        propagatedBuildInputs = [ pkgs.python3Packages.pyqt5 ];
        checkInputs = [ pkgs.python3Packages.pytest ];
        checkPhase = ''
          pytest -k 'test_qthreadexec.py' # the others cause the test execution to be aborted, I think because of asyncio
        '';
      };

      outputcheck = pkgs.python3Packages.buildPythonApplication rec {
        pname = "outputcheck";
        version = "0.4.2";
        src = pkgs.fetchFromGitHub {
          owner = "stp";
          repo = "OutputCheck";
          rev = "e0f533d3c5af2949349856c711bf4bca50022b48";
          sha256 = "1y27vz6jq6sywas07kz3v01sqjd0sga9yv9w2cksqac3v7wmf2a0";
        };
        prePatch = "echo ${version} > RELEASE-VERSION";
      };

      libartiq-support = pkgs.stdenv.mkDerivation {
        name = "libartiq-support";
        src = self;
        buildInputs = [ rustPlatform.rust.rustc ];
        buildPhase = ''
          rustc $src/artiq/test/libartiq_support/lib.rs -Cpanic=unwind -g
        '';
        installPhase = ''
          mkdir -p $out/lib $out/bin
          cp libartiq_support.so $out/lib
          cat > $out/bin/libartiq-support << EOF
          #!/bin/sh
          echo $out/lib/libartiq_support.so
          EOF
          chmod 755 $out/bin/libartiq-support
        '';
      };

      llvmlite-new = pkgs.python3Packages.buildPythonPackage rec {
        pname = "llvmlite";
        version = "0.38.0";
        src = pkgs.python3Packages.fetchPypi {
          inherit pname;
          version = "0.38.0";
          sha256 = "qZ0WbM87EW87ntI7m3C6JBVkCpyXjzqqE/rUnFj0llw=";
        };
        nativeBuildInputs = [ pkgs.llvm_11 ];
        # Disable static linking
        # https://github.com/numba/llvmlite/issues/93
        postPatch = ''
          substituteInPlace ffi/Makefile.linux --replace "-static-libstdc++" ""
          substituteInPlace llvmlite/tests/test_binding.py --replace "test_linux" "nope"
        '';
        # Set directory containing llvm-config binary
        preConfigure = ''
          export LLVM_CONFIG=${pkgs.llvm_11.dev}/bin/llvm-config
        '';
        doCheck = false;  # FIXME
      };

      artiq-upstream = pkgs.python3Packages.buildPythonPackage rec {
        pname = "artiq";
        version = artiqVersion;
        src = self;

        preBuild =
          ''
          export VERSIONEER_OVERRIDE=${version}
          export VERSIONEER_REV=${artiqRev}
          '';

        nativeBuildInputs = [ pkgs.qt5.wrapQtAppsHook ];
        # keep llvm_x and lld_x in sync with llvmlite
        propagatedBuildInputs = [ pkgs.llvm_11 pkgs.lld_11 llvmlite-new sipyco.packages.x86_64-linux.sipyco pythonparser artiq-comtools.packages.x86_64-linux.artiq-comtools ]
          ++ (with pkgs.python3Packages; [ pyqtgraph pygit2 numpy dateutil scipy prettytable pyserial python-Levenshtein h5py pyqt5 qasync tqdm ]);

        dontWrapQtApps = true;
        postFixup = ''
          wrapQtApp "$out/bin/artiq_dashboard"
          wrapQtApp "$out/bin/artiq_browser"
          wrapQtApp "$out/bin/artiq_session"
        '';

        # Modifies PATH to pass the wrapped python environment (i.e. python3.withPackages(...) to subprocesses.
        # Allows subprocesses using python to find all packages you have installed
        makeWrapperArgs = [
          ''--run 'if [ ! -z "$NIX_PYTHONPREFIX" ]; then export PATH=$NIX_PYTHONPREFIX/bin:$PATH;fi' ''
          "--set FONTCONFIG_FILE ${pkgs.fontconfig.out}/etc/fonts/fonts.conf"
        ];

        # FIXME: automatically propagate lld_11 llvm_11 dependencies
        checkInputs = [ pkgs.lld_11 pkgs.llvm_11 libartiq-support pkgs.lit outputcheck ];
        checkPhase = ''
          python -m unittest discover -v artiq.test

          TESTDIR=`mktemp -d`
          cp --no-preserve=mode,ownership -R $src/artiq/test/lit $TESTDIR
          LIBARTIQ_SUPPORT=`libartiq-support` lit -v $TESTDIR/lit
          '';
      };

      artiq = artiq-upstream // {
        withExperimentalFeatures = features: artiq-upstream.overrideAttrs(oa:
            { patches = map (f: ./experimental-features/${f}.diff) features; });
      };

      migen = pkgs.python3Packages.buildPythonPackage rec {
        name = "migen";
        src = src-migen;
        propagatedBuildInputs = [ pkgs.python3Packages.colorama ];
      };

      asyncserial = pkgs.python3Packages.buildPythonPackage rec {
        pname = "asyncserial";
        version = "0.1";
        src = pkgs.fetchFromGitHub {
          owner = "m-labs";
          repo = "asyncserial";
          rev = "d95bc1d6c791b0e9785935d2f62f628eb5cdf98d";
          sha256 = "0yzkka9jk3612v8gx748x6ziwykq5lr7zmr9wzkcls0v2yilqx9k";
        };
        propagatedBuildInputs = [ pkgs.python3Packages.pyserial ];
      };

      misoc = pkgs.python3Packages.buildPythonPackage {
        name = "misoc";
        src = src-misoc;
        propagatedBuildInputs = with pkgs.python3Packages; [ jinja2 numpy migen pyserial asyncserial ];
      };

      jesd204b = pkgs.python3Packages.buildPythonPackage rec {
        pname = "jesd204b";
        version = "unstable-2021-05-05";
        src = pkgs.fetchFromGitHub {
          owner = "m-labs";
          repo = "jesd204b";
          rev = "bf1cd9014c8b7a9db67609f653634daaf3bcd39b";
          sha256 = "sha256-wyYOCRIPANReeCl+KaIpiAStsn2mzfMlK+cSrUzVrAw=";
        };
        propagatedBuildInputs = with pkgs.python3Packages; [ migen misoc ];
      };

      microscope = pkgs.python3Packages.buildPythonPackage rec {
        pname = "microscope";
        version = "unstable-2020-12-28";
        src = pkgs.fetchFromGitHub {
          owner = "m-labs";
          repo = "microscope";
          rev = "c21afe7a53258f05bde57e5ebf2e2761f3d495e4";
          sha256 = "sha256-jzyiLRuEf7p8LdhmZvOQj/dyQx8eUE8p6uRlwoiT8vg=";
        };
        propagatedBuildInputs = with pkgs.python3Packages; [ pyserial prettytable msgpack migen ];
      };

      cargo-xbuild = rustPlatform.buildRustPackage rec {
        pname = "cargo-xbuild";
        version = "0.6.5";

        src = pkgs.fetchFromGitHub {
          owner = "rust-osdev";
          repo = pname;
          rev = "v${version}";
          sha256 = "18djvygq9v8rmfchvi2hfj0i6fhn36m716vqndqnj56fiqviwxvf";
        };

        cargoSha256 = "13sj9j9kl6js75h9xq0yidxy63vixxm9q3f8jil6ymarml5wkhx8";
      };

      vivadoEnv = pkgs.buildFHSUserEnv {
        name = "vivado-env";
        targetPkgs = vivadoDeps;
      };

      vivado = pkgs.buildFHSUserEnv {
        name = "vivado";
        targetPkgs = vivadoDeps;
        profile = "set -e; source /opt/Xilinx/Vivado/2021.2/settings64.sh";
        runScript = "vivado";
      };

      makeArtiqBoardPackage = { target, variant, buildCommand ? "python -m artiq.gateware.targets.${target} -V ${variant}", experimentalFeatures ? [] }:
        pkgs.stdenv.mkDerivation {
          name = "artiq-board-${target}-${variant}";
          phases = [ "buildPhase" "checkPhase" "installPhase" ];
          cargoDeps = rustPlatform.importCargoLock {
            lockFile = ./artiq/firmware/Cargo.lock;
            outputHashes = {
              "fringe-1.2.1" = "sha256-m4rzttWXRlwx53LWYpaKuU5AZe4GSkbjHS6oINt5d3Y=";
            };
          };
          nativeBuildInputs = [
            (pkgs.python3.withPackages(ps: [ ps.jsonschema migen misoc (artiq.withExperimentalFeatures experimentalFeatures) ]))
            rustPlatform.rust.rustc
            rustPlatform.rust.cargo
            pkgs.llvmPackages_11.clang-unwrapped
            pkgs.llvm_11
            pkgs.lld_11
            vivado
            rustPlatform.cargoSetupHook
            cargo-xbuild
          ];
          buildPhase = 
            ''
            ARTIQ_PATH=`python -c "import artiq; print(artiq.__path__[0])"`
            ln -s $ARTIQ_PATH/firmware/Cargo.lock .
            cargoSetupPostUnpackHook
            cargoSetupPostPatchHook
            ${buildCommand}
            '';
          doCheck = true;
          checkPhase =
            ''
            # Search for PCREs in the Vivado output to check for errors
            check_log() {
              grep -Pe "$1" artiq_${target}/${variant}/gateware/vivado.log && exit 1 || true
            }
            check_log "\d+ constraint not met\."
            check_log "Timing constraints are not met\."
            '';
          installPhase =
            ''
            TARGET_DIR=$out
            mkdir -p $TARGET_DIR
            cp artiq_${target}/${variant}/gateware/top.bit $TARGET_DIR
            if [ -e artiq_${target}/${variant}/software/bootloader/bootloader.bin ]
            then cp artiq_${target}/${variant}/software/bootloader/bootloader.bin $TARGET_DIR
            fi
            if [ -e artiq_${target}/${variant}/software/runtime ]
            then cp artiq_${target}/${variant}/software/runtime/runtime.{elf,fbi} $TARGET_DIR
            else cp artiq_${target}/${variant}/software/satman/satman.{elf,fbi} $TARGET_DIR
            fi
            '';
          # don't mangle ELF files as they are not for NixOS
          dontFixup = true;
        };

      openocd-bscanspi-f = pkgs: let
        bscan_spi_bitstreams-pkg = pkgs.stdenv.mkDerivation {
          name = "bscan_spi_bitstreams";
          src = pkgs.fetchFromGitHub {
            owner = "quartiq";
            repo = "bscan_spi_bitstreams";
            rev = "01d8f819f15baf9a8cc5d96945a51e4d267ff564";
            sha256 = "1zqv47kzgvbn4c8cr019a6wcja7gn5h1z4kvw5bhpc72fyhagal9";
          };
          phases = ["installPhase"];
          installPhase =
          ''
          mkdir -p $out/share/bscan-spi-bitstreams
          cp $src/*.bit $out/share/bscan-spi-bitstreams
          '';
        };
        # https://docs.lambdaconcept.com/screamer/troubleshooting.html#error-contents-differ
        openocd-fixed = pkgs.openocd.overrideAttrs(oa: {
          version = "unstable-2021-09-15";
          src = pkgs.fetchFromGitHub {
            owner = "openocd-org";
            repo = "openocd";
            rev = "a0bd3c9924870c3b8f428648410181040dabc33c";
            sha256 = "sha256-YgUsl4/FohfsOncM4uiz/3c6g2ZN4oZ0y5vV/2Skwqg=";
            fetchSubmodules = true;
          };
          patches = [
            (pkgs.fetchurl {
              url = "https://git.m-labs.hk/M-Labs/nix-scripts/raw/commit/575ef05cd554c239e4cc8cb97ae4611db458a80d/artiq-fast/pkgs/openocd-jtagspi.diff";
              sha256 = "0g3crk8gby42gm661yxdcgapdi8sp050l5pb2d0yjfic7ns9cw81";
            })
          ];
          nativeBuildInputs = oa.nativeBuildInputs or [] ++ [ pkgs.autoreconfHook269 ];
        });
      in pkgs.buildEnv {
        name = "openocd-bscanspi";
        paths = [ openocd-fixed bscan_spi_bitstreams-pkg ];
      };

      sphinxcontrib-wavedrom = pkgs.python3Packages.buildPythonPackage rec {
        pname = "sphinxcontrib-wavedrom";
        version = "3.0.2";
        src = pkgs.python3Packages.fetchPypi {
          inherit pname version;
          sha256 = "sha256-ukZd3ajt0Sx3LByof4R80S31F5t1yo+L8QUADrMMm2A=";
        };
        buildInputs = [ pkgs.python3Packages.setuptools_scm ];
        propagatedBuildInputs = (with pkgs.python3Packages; [ wavedrom sphinx xcffib cairosvg ]);
      };
      latex-artiq-manual = pkgs.texlive.combine {
        inherit (pkgs.texlive)
          scheme-basic latexmk cmap collection-fontsrecommended fncychap
          titlesec tabulary varwidth framed fancyvrb float wrapfig parskip
          upquote capt-of needspace etoolbox;
      };
    in rec {
      packages.x86_64-linux = {
        inherit pythonparser qasync artiq;
        inherit migen misoc asyncserial microscope vivadoEnv vivado;
        openocd-bscanspi = openocd-bscanspi-f pkgs;
        artiq-board-kc705-nist_clock = makeArtiqBoardPackage {
          target = "kc705";
          variant = "nist_clock";
        };
        inherit sphinxcontrib-wavedrom latex-artiq-manual;
        artiq-manual-html = pkgs.stdenvNoCC.mkDerivation rec {
          name = "artiq-manual-html-${version}";
          version = artiqVersion;
          src = self;
          buildInputs = [
            pkgs.python3Packages.sphinx pkgs.python3Packages.sphinx_rtd_theme
            pkgs.python3Packages.sphinx-argparse sphinxcontrib-wavedrom
          ];
          buildPhase = ''
            export VERSIONEER_OVERRIDE=${artiqVersion}
            export SOURCE_DATE_EPOCH=${builtins.toString self.sourceInfo.lastModified}
            cd doc/manual
            make html
          '';
          installPhase = ''
            cp -r _build/html $out
            mkdir $out/nix-support
            echo doc manual $out index.html >> $out/nix-support/hydra-build-products
          '';
        };
        artiq-manual-pdf = pkgs.stdenvNoCC.mkDerivation rec {
          name = "artiq-manual-pdf-${version}";
          version = artiqVersion;
          src = self;
          buildInputs = [
            pkgs.python3Packages.sphinx pkgs.python3Packages.sphinx_rtd_theme
            pkgs.python3Packages.sphinx-argparse sphinxcontrib-wavedrom
            latex-artiq-manual
          ];
          buildPhase = ''
            export VERSIONEER_OVERRIDE=${artiq.version}
            export SOURCE_DATE_EPOCH=${builtins.toString self.sourceInfo.lastModified}
            cd doc/manual
            make latexpdf
          '';
          installPhase = ''
            mkdir $out
            cp _build/latex/ARTIQ.pdf $out
            mkdir $out/nix-support
            echo doc-pdf manual $out ARTIQ.pdf >> $out/nix-support/hydra-build-products
          '';
        };
      };

      inherit makeArtiqBoardPackage;

      defaultPackage.x86_64-linux = pkgs.python3.withPackages(ps: [ packages.x86_64-linux.artiq ]);

      devShell.x86_64-linux = pkgs.mkShell {
        name = "artiq-dev-shell";
        buildInputs = [
          (pkgs.python3.withPackages(ps: with packages.x86_64-linux; [ migen misoc jesd204b artiq ps.paramiko ps.jsonschema microscope ]))
          rustPlatform.rust.rustc
          rustPlatform.rust.cargo
          cargo-xbuild
          pkgs.llvmPackages_11.clang-unwrapped
          pkgs.llvm_11
          pkgs.lld_11
          # To manually run compiler tests:
          pkgs.lit
          outputcheck
          libartiq-support
          # use the vivado-env command to enter a FHS shell that lets you run the Vivado installer
          packages.x86_64-linux.vivadoEnv
          packages.x86_64-linux.vivado
          packages.x86_64-linux.openocd-bscanspi
          pkgs.python3Packages.sphinx pkgs.python3Packages.sphinx_rtd_theme
          pkgs.python3Packages.sphinx-argparse sphinxcontrib-wavedrom latex-artiq-manual
        ];
        shellHook = ''
          export LIBARTIQ_SUPPORT=`libartiq-support`
	  export QT_PLUGIN_PATH=${pkgs.qt5.qtbase}/${pkgs.qt5.qtbase.dev.qtPluginPrefix}
          export QML2_IMPORT_PATH=${pkgs.qt5.qtbase}/${pkgs.qt5.qtbase.dev.qtQmlPrefix}
        '';
      };

      packages.aarch64-linux = {
        openocd-bscanspi = openocd-bscanspi-f pkgs-aarch64;
      };

      hydraJobs = {
        inherit (packages.x86_64-linux) artiq artiq-board-kc705-nist_clock openocd-bscanspi;
        kc705-hitl = pkgs.stdenv.mkDerivation {
          name = "kc705-hitl";

          __networked = true;  # compatibility with old patched Nix
          # breaks hydra, https://github.com/NixOS/hydra/issues/1216
          #__impure = true;     # Nix 2.8+

          buildInputs = [
            (pkgs.python3.withPackages(ps: with packages.x86_64-linux; [ artiq ps.paramiko ]))
            pkgs.llvm_11
            pkgs.lld_11
            pkgs.openssh
            packages.x86_64-linux.openocd-bscanspi  # for the bscanspi bitstreams
          ];
          phases = [ "buildPhase" ];
          buildPhase =
            ''
            whoami
            export HOME=`mktemp -d`
            mkdir $HOME/.ssh
            cp /opt/hydra_id_ed25519 $HOME/.ssh/id_ed25519
            cp /opt/hydra_id_ed25519.pub $HOME/.ssh/id_ed25519.pub
            echo "rpi-1 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIACtBFDVBYoAE4fpJCTANZSE0bcVpTR3uvfNvb80C4i5" > $HOME/.ssh/known_hosts
            chmod 600 $HOME/.ssh/id_ed25519
            LOCKCTL=$(mktemp -d)
            mkfifo $LOCKCTL/lockctl

            cat $LOCKCTL/lockctl | ${pkgs.openssh}/bin/ssh \
              -i $HOME/.ssh/id_ed25519 \
              -o UserKnownHostsFile=$HOME/.ssh/known_hosts \
              rpi-1 \
              'mkdir -p /tmp/board_lock && flock /tmp/board_lock/kc705-1 -c "echo Ok; cat"' \
            | (
              # End remote flock via FIFO
              atexit_unlock() {
                echo > $LOCKCTL/lockctl
              }
              trap atexit_unlock EXIT

              # Read "Ok" line when remote successfully locked
              read LOCK_OK

              artiq_flash -t kc705 -H rpi-1 -d ${packages.x86_64-linux.artiq-board-kc705-nist_clock}
              sleep 15

              export ARTIQ_ROOT=`python -c "import artiq; print(artiq.__path__[0])"`/examples/kc705_nist_clock
              export ARTIQ_LOW_LATENCY=1
              python -m unittest discover -v artiq.test.coredevice
            )

            touch $out
            '';
        };
        inherit (packages.x86_64-linux) artiq-manual-html artiq-manual-pdf;
      };
    };

  nixConfig = {
    extra-trusted-public-keys = "nixbld.m-labs.hk-1:5aSRVA5b320xbNvu30tqxVPXpld73bhtOeH6uAjRyHc=";
    extra-substituters = "https://nixbld.m-labs.hk";
    extra-sandbox-paths = "/opt";
  };
}
