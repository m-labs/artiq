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
            LIBARTIQ_SUPPORT=${libartiq-support}/libartiq_support.so lit -v $TESTDIR/lit
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
          profile = "source /opt/Xilinx/Vivado/2020.1/settings64.sh";
          runScript = "vivado";
        };

        artiq-board-kc705-nist_clock = let
          makeArtiqBoardPackage = { target, variant, buildCommand ? "python -m artiq.gateware.targets.${target} -V ${variant}" }:
            pkgs.python3Packages.toPythonModule (pkgs.stdenv.mkDerivation {
              name = "artiq-board-${target}-${variant}";
              phases = [ "buildPhase" "checkPhase" "installPhase" ];
              cargoDeps = rustPlatform.fetchCargoTarball {
                name = "artiq-firmware-cargo-deps";
                src = "${self}/artiq/firmware";
                sha256 = "0hh9x34gs81a8g15abka6a0z1wlankra13rbap5j7ba2r8cz4962";
              };
              nativeBuildInputs = [
                (pkgs.python3.withPackages(ps: [ migen misoc artiq ]))
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
                TARGET_DIR=$out/${pkgs.python3Packages.python.sitePackages}/artiq/board-support/${target}-${variant}
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
            });
        in makeArtiqBoardPackage {
          target = "kc705";
          variant = "nist_clock";
        };

        openocd-bscanspi = let
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
            patches = oa.patches or [] ++ [
              (pkgs.fetchurl {
                url = "https://docs.lambdaconcept.com/screamer/_downloads/f0357c5f44c3c8c49f575cee5b6634a8/flashid.patch";
                sha256 = "015h4fzdrpwy5ssqbpk826snnfkkqijkmjzr5ws0a2v0ci97jzm9";
              })
            ];
          });
        in pkgs.buildEnv {
          name = "openocd-bscanspi";
          paths = [ openocd-fixed bscan_spi_bitstreams-pkg ];
        };
      };

      defaultPackage.x86_64-linux = pkgs.python3.withPackages(ps: [ packages.x86_64-linux.artiq ]);

      devShell.x86_64-linux = pkgs.mkShell {
        name = "artiq-dev-shell";
        buildInputs = [
          (pkgs.python3.withPackages(ps: with packages.x86_64-linux; [ migen misoc artiq ps.paramiko ]))
          rustPlatform.rust.rustc
          rustPlatform.rust.cargo
          pkgs.llvmPackages_11.clang-unwrapped
          pkgs.llvm_11
          pkgs.lld_11
          # use the vivado-env command to enter a FHS shell that lets you run the Vivado installer
          packages.x86_64-linux.vivadoEnv
          packages.x86_64-linux.vivado
          packages.x86_64-linux.openocd-bscanspi
        ];
        TARGET_AR="llvm-ar";
      };

      hydraJobs = {
        inherit (packages.x86_64-linux) artiq artiq-board-kc705-nist_clock openocd-bscanspi;
        kc705-hitl = pkgs.stdenv.mkDerivation {
          name = "kc705-hitl";

          # requires patched Nix
          __networked = true;

          buildInputs = [
            (pkgs.python3.withPackages(ps: with packages.x86_64-linux; [ artiq artiq-board-kc705-nist_clock ps.paramiko ]))
            pkgs.llvm_11
            pkgs.lld_11
            pkgs.openssh
            packages.x86_64-linux.openocd-bscanspi  # for the bscanspi bitstreams
          ];
          phases = [ "buildPhase" ];
          buildPhase =
            ''
            export HOME=`mktemp -d`
            mkdir $HOME/.ssh
            cp /opt/hydra_id_rsa $HOME/.ssh/id_rsa
            cp /opt/hydra_id_rsa.pub $HOME/.ssh/id_rsa.pub
            echo "rpi-1 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIPOBQVcsvk6WgRj18v4m0zkFeKrcN9gA+r6sxQxNwFpv" > $HOME/.ssh/known_hosts
            chmod 600 $HOME/.ssh/id_rsa
            LOCKCTL=$(mktemp -d)
            mkfifo $LOCKCTL/lockctl

            cat $LOCKCTL/lockctl | ${pkgs.openssh}/bin/ssh \
              -i $HOME/.ssh/id_rsa \
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

              artiq_flash -t kc705 -H rpi-1
              sleep 15

              export ARTIQ_ROOT=`python -c "import artiq; print(artiq.__path__[0])"`/examples/kc705_nist_clock
              export ARTIQ_LOW_LATENCY=1
              python -m unittest discover -v artiq.test.coredevice
            )

            touch $out
            '';
        };
      };
    };

  nixConfig = {
    binaryCachePublicKeys = ["nixbld.m-labs.hk-1:5aSRVA5b320xbNvu30tqxVPXpld73bhtOeH6uAjRyHc="];
    binaryCaches = ["https://nixbld.m-labs.hk" "https://cache.nixos.org"];
    sandboxPaths = ["/opt"];
  };
}
