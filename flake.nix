{
  description = "A leading-edge control system for quantum information experiments";

  inputs.nixpkgs.url = github:NixOS/nixpkgs/nixos-21.05;
  inputs.src-sipyco = { url = github:m-labs/sipyco; flake = false; };
  inputs.src-pythonparser = { url = github:m-labs/pythonparser; flake = false; };

  outputs = { self, nixpkgs, src-sipyco, src-pythonparser }: with import nixpkgs { system = "x86_64-linux"; }; rec {
    packages.x86_64-linux = rec {
      sipyco = python3Packages.buildPythonPackage {
        name = "sipyco";
        src = src-sipyco;
        propagatedBuildInputs = with python3Packages; [ pybase64 numpy ];
      };

      pythonparser = python3Packages.buildPythonPackage {
        name = "pythonparser";
        src = src-pythonparser;
        doCheck = false;
        propagatedBuildInputs = with python3Packages; [ regex ];
      };

      qasync = python3Packages.buildPythonPackage rec {
        pname = "qasync";
        version = "0.10.0";
        src = fetchFromGitHub {
          owner = "CabbageDevelopment";
          repo = "qasync";
          rev = "v${version}";
          sha256 = "1zga8s6dr7gk6awmxkh4pf25gbg8n6dv1j4b0by7y0fhi949qakq";
        };
        propagatedBuildInputs = [ python3Packages.pyqt5 ];
        checkInputs = [ python3Packages.pytest ];
        checkPhase = ''
          pytest -k 'test_qthreadexec.py' # the others cause the test execution to be aborted, I think because of asyncio
        '';
      };

      outputcheck = python3Packages.buildPythonApplication rec {
        pname = "outputcheck";
        version = "0.4.2";
        src = fetchFromGitHub {
          owner = "stp";
          repo = "OutputCheck";
          rev = "e0f533d3c5af2949349856c711bf4bca50022b48";
          sha256 = "1y27vz6jq6sywas07kz3v01sqjd0sga9yv9w2cksqac3v7wmf2a0";
        };
        prePatch = "echo ${version} > RELEASE-VERSION";
      };

      libartiq-support = stdenv.mkDerivation {
        name = "libartiq-support";
        src = self;
        buildInputs = [ rustc ];
        buildPhase = ''
          # Obviously, #[feature()] can in fact be used on the stable channel, contrary to what the rustc error message says.
          # You just need to set this obscure RUSTC_BOOTSTRAP environment variable.
          RUSTC_BOOTSTRAP=1 rustc $src/artiq/test/libartiq_support/lib.rs -Cpanic=unwind -g
        '';
        installPhase = ''
          mkdir $out
          cp libartiq_support.so $out
        '';
      };

      artiq = python3Packages.buildPythonPackage rec {
        pname = "artiq";
        version = "7.0-dev";
        src = self;

        preBuild = "export VERSIONEER_OVERRIDE=${version}";

        nativeBuildInputs = [ qt5.wrapQtAppsHook ];
        # keep llvm_x and lld_x in sync with llvmlite
        propagatedBuildInputs = [ llvm_9 lld_9 sipyco pythonparser ]
          ++ (with python3Packages; [ pyqtgraph pygit2 numpy dateutil scipy prettytable pyserial python-Levenshtein h5py pyqt5 qasync llvmlite ]);

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
          "--set FONTCONFIG_FILE ${fontconfig.out}/etc/fonts/fonts.conf"
        ];

        # FIXME: automatically propagate lld_9 llvm_9 dependencies
        checkInputs = [ lld_9 llvm_9 outputcheck lit ];
        checkPhase = ''
          python -m unittest discover -v artiq.test

          TESTDIR=`mktemp -d`
          cp --no-preserve=mode,ownership -R $src/artiq/test/lit $TESTDIR
          # FIXME: some tests fail
          #LIBARTIQ_SUPPORT=${libartiq-support}/libartiq_support.so lit -v $TESTDIR/lit
          '';
      };
    };

    defaultPackage.x86_64-linux = python3.withPackages(ps: [ packages.x86_64-linux.artiq ]);
  };
}
