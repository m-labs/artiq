{
  description = "A leading-edge control system for quantum information experiments";

  inputs.nixpkgs.url = github:NixOS/nixpkgs/nixos-21.05;
  inputs.mozilla-overlay = { url = github:mozilla/nixpkgs-mozilla; flake = false; };
  inputs.src-sipyco = { url = github:m-labs/sipyco; flake = false; };
  inputs.src-pythonparser = { url = github:m-labs/pythonparser; flake = false; };

  inputs.src-migen = { url = github:m-labs/migen; flake = false; };
  inputs.src-misoc = { type = "git"; url = "https://github.com/m-labs/misoc.git"; submodules = true; flake = false; };

  outputs = { self, nixpkgs, mozilla-overlay, src-sipyco, src-pythonparser, src-migen, src-misoc }:
    let
      pkgs = import nixpkgs { system = "x86_64-linux"; overlays = [ (import mozilla-overlay) ]; };
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
      ];
      # TODO: cargo-vendor-normalise
      fetchcargo = { name, src, sha256 }:
        pkgs.stdenv.mkDerivation {
          name = "${name}-vendor";
          strictDeps = true;
          nativeBuildInputs = with pkgs; [ cacert git cargo ];
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

            mkdir -p $out
            export CARGO_HOME=$(mktemp -d cargo-home.XXX)

            cargo vendor > $out/config

            cp -ar vendor $out/vendor
          '';

          outputHashAlgo = "sha256";
          outputHashMode = "recursive";
          outputHash = sha256;

          impureEnvVars = pkgs.lib.fetchers.proxyImpureEnvVars;
          preferLocalBuild = true;
        };
    in rec {
      packages.x86_64-linux = rec {
        sipyco = pkgs.python3Packages.buildPythonPackage {
          name = "sipyco";
          src = src-sipyco;
          propagatedBuildInputs = with pkgs.python3Packages; [ pybase64 numpy ];
        };

        pythonparser = pkgs.python3Packages.buildPythonPackage {
          name = "pythonparser";
          src = src-pythonparser;
          doCheck = false;
          propagatedBuildInputs = with pkgs.python3Packages; [ regex ];
        };

        qasync = pkgs.python3Packages.buildPythonPackage rec {
          pname = "qasync";
          version = "0.10.0";
          src = pkgs.fetchFromGitHub {
            owner = "CabbageDevelopment";
            repo = "qasync";
            rev = "v${version}";
            sha256 = "1zga8s6dr7gk6awmxkh4pf25gbg8n6dv1j4b0by7y0fhi949qakq";
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
            mkdir $out
            cp libartiq_support.so $out
          '';
        };

        llvmlite-new = pkgs.python3Packages.buildPythonPackage rec {
          pname = "llvmlite";
          version = "0.37.0rc2";
          src = pkgs.python3Packages.fetchPypi {
            inherit pname version;
            sha256 = "sha256-F1quz+76JOt1jaQPVzdKe7RfN6gWG2lyE82qTvgyY/c=";
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

        artiq = pkgs.python3Packages.buildPythonPackage rec {
          pname = "artiq";
          version = "7.0-dev";
          src = self;

          preBuild = "export VERSIONEER_OVERRIDE=${version}";

          nativeBuildInputs = [ pkgs.qt5.wrapQtAppsHook ];
          # keep llvm_x and lld_x in sync with llvmlite
          propagatedBuildInputs = [ pkgs.llvm_11 pkgs.lld_11 llvmlite-new sipyco pythonparser ]
            ++ (with pkgs.python3Packages; [ pyqtgraph pygit2 numpy dateutil scipy prettytable pyserial python-Levenshtein h5py pyqt5 qasync ]);

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
          checkInputs = [ pkgs.lld_11 pkgs.llvm_11 pkgs.lit outputcheck ];
          checkPhase = ''
            python -m unittest discover -v artiq.test

            TESTDIR=`mktemp -d`
            cp --no-preserve=mode,ownership -R $src/artiq/test/lit $TESTDIR
            # FIXME: some tests fail
            #LIBARTIQ_SUPPORT=${libartiq-support}/libartiq_support.so lit -v $TESTDIR/lit
            '';
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
          doCheck = false;  # TODO: fix misoc bitrot and re-enable tests
          propagatedBuildInputs = with pkgs.python3Packages; [ jinja2 numpy migen pyserial asyncserial ];
        };

        vivadoEnv = pkgs.buildFHSUserEnv {
          name = "vivado-env";
          targetPkgs = vivadoDeps;
        };

        vivado = pkgs.buildFHSUserEnv {
          name = "vivado";
          targetPkgs = vivadoDeps;
          profile = "source /opt/Xilinx/Vivado/2020.1/settings64.sh";
          runScript = "vivado";
        };

        artiq-board-kc705-nist-clock = let
          cargoVendored = fetchcargo {
            name = "artiq-firmware-cargo-deps";
            src = "${self}/artiq/firmware";
            sha256 = "0vbh18v72y2qirba8sfg08kzx0crykg28jyi65mjpqacavfz89d8";
          };
          makeArtiqBoardPackage = { target, variant, buildCommand ? "python -m artiq.gateware.targets.${target} -V ${variant}" }:
            pkgs.stdenv.mkDerivation {
              name = "artiq-board-${target}-${variant}";
              phases = [ "buildPhase" "checkPhase" "installPhase" ];
              nativeBuildInputs = [
                (pkgs.python3.withPackages(ps: [ migen misoc artiq ]))
                rustPlatform.rust.rustc
                rustPlatform.rust.cargo
                pkgs.llvmPackages_11.clang-unwrapped
                pkgs.llvm_11
                pkgs.lld_11
                vivado
              ];
              buildPhase = 
                ''
                export CARGO_HOME=${cargoVendored}
                export TARGET_AR=llvm-ar
                ${buildCommand}
                '';
              checkPhase = ''
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
        in makeArtiqBoardPackage {
          target = "kc705";
          variant = "nist_clock";
        };
      };

      defaultPackage.x86_64-linux = pkgs.python3.withPackages(ps: [ packages.x86_64-linux.artiq ]);

      devShell.x86_64-linux = pkgs.mkShell {
        name = "artiq-dev-shell";
        buildInputs = [
          (pkgs.python3.withPackages(ps: with packages.x86_64-linux; [ migen misoc artiq ]))
          rustPlatform.rust.rustc
          rustPlatform.rust.cargo
          pkgs.llvmPackages_11.clang-unwrapped
          pkgs.llvm_11
          pkgs.lld_11
          # use the vivado-env command to enter a FHS shell that lets you run the Vivado installer
          packages.x86_64-linux.vivadoEnv
          packages.x86_64-linux.vivado
        ];
        TARGET_AR="llvm-ar";
      };

      hydraJobs = {
        artiq = packages.x86_64-linux.artiq;
      };
    };

  nixConfig = {
    binaryCachePublicKeys = ["nixbld.m-labs.hk-1:5aSRVA5b320xbNvu30tqxVPXpld73bhtOeH6uAjRyHc="];
    binaryCaches = ["https://nixbld.m-labs.hk" "https://cache.nixos.org"];
    sandboxPaths = ["/opt"];
  };
}
