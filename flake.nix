{
  description = "A leading-edge control system for quantum information experiments";

  inputs.nixpkgs.url = github:NixOS/nixpkgs/nixos-21.05;
  inputs.mozilla-overlay = { url = github:mozilla/nixpkgs-mozilla; flake = false; };
  inputs.src-sipyco = { url = github:m-labs/sipyco; flake = false; };
  inputs.src-pythonparser = { url = github:m-labs/pythonparser; flake = false; };

  inputs.src-migen = { url = github:m-labs/migen; flake = false; };
  inputs.src-misoc = { url = github:m-labs/misoc; flake = false; };

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
        ];
        TARGET_AR="llvm-ar";
      };
    };

  nixConfig = {
    binaryCachePublicKeys = ["nixbld.m-labs.hk-1:5aSRVA5b320xbNvu30tqxVPXpld73bhtOeH6uAjRyHc="];
    binaryCaches = ["https://nixbld.m-labs.hk" "https://cache.nixos.org"];
  };
}
