{ stdenv, fetchFromGitHub, fetchsvn, python3Packages, qt5Full, llvm-or1k, llvmlite, python3}:

let

levenshtein = python3Packages.buildPythonPackage rec {
  name = "levenshtein";
  src = fetchFromGitHub {
    owner = "ztane";
    repo = "python-Levenshtein";
    rev = "854e61a05bb8b750e990add96df412cd5448b75e";
    sha256 = "1yf21kg1g2ivm5a4dx1jra9k0c33np54d0hk5ymnfyc4f6pg386q";
  };
  doCheck = false;
};

pythonparser = python3Packages.buildPythonPackage rec {
  name = "pythonparser";
  src = fetchFromGitHub {
    owner = "m-labs";
    repo = "pythonparser";
    rev = "8bdc7badbd08e2196b864e12889ea9191ca6e09c";
    sha256 = "1f538wnjlqah0dsvq256k2rv7s7bffsvjcxy8fq0x3a4g0s6pm9d";
  };
  propagatedBuildInputs = with python3Packages; [ regex ];
  doCheck = false;
};

asyncserial = python3Packages.buildPythonPackage rec {
  name = "asyncserial";
  src = fetchFromGitHub {
    owner = "m-labs";
    repo = "asyncserial";
    rev = "d95bc1d6c791b0e9785935d2f62f628eb5cdf98d";
    sha256 = "0yzkka9jk3612v8gx748x6ziwykq5lr7zmr9wzkcls0v2yilqx9k";
  };
  propagatedBuildInputs = with python3Packages; [ pyserial ];
  doCheck = false;
};

outputcheck = python3Packages.buildPythonPackage rec {
  name = "outputcheck";
  version = "0.4.2";
  src = fetchFromGitHub {
    owner = "stp";
    repo = "OutputCheck";
    rev = "e0f533d3c5af2949349856c711bf4bca50022b48";
    sha256 = "1y27vz6jq6sywas07kz3v01sqjd0sga9yv9w2cksqac3v7wmf2a0";
  };
  prePatch = ''
  substituteInPlace setup.py \
  --replace "version.get_git_version()" "\"${version}\"" \
  --replace "import version" ""
  '';
  doCheck = false;
};

quamash = python3Packages.buildPythonPackage rec {
  name = "quamash";
  src = fetchFromGitHub {
    owner = "harvimt";
    repo = "quamash";
    rev = "bbab9e30e10b71a95687b03a93524173fb7b43f0";
    sha256 = "08hp2q4ifj6z2ww05c7zsy0cd732k9rnaims1j43vr4hhxx950mk";
  };
  propagatedBuildInputs = with python3Packages; [ pyqt5 ];
  doCheck = false;
};

pyqtgraph-qt5 = python3Packages.buildPythonPackage rec {
  name = "pyqtgraph_qt5-${version}";
  version = "0.10.0";
  doCheck = false;
  src = fetchFromGitHub {
    owner = "pyqtgraph";
    repo = "pyqtgraph";
    rev = "1426e334e1d20542400d77c72c132b04c6d17ddb";
    sha256 = "1079haxyr316jf0wpirxdj0ry6j8mr16cqr0dyyrd5cnxwl7zssh";
  };
  propagatedBuildInputs = with python3Packages; [ scipy numpy pyqt5 pyopengl ];
};

lit = python3Packages.buildPythonPackage rec {
  name = "lit";
  version = "262719";
  source = fetchsvn {
    url = "http://llvm.org/svn/llvm-project/llvm/trunk/";
    rev = "${version}";
    sha256 = "1iashczfh30v9ark4xijk6z2q07c1kb70nar00mwnfix77gkb2v6";
  };
  src = source + /utils/lit;
  doCheck = false;
};

in

python3Packages.buildPythonPackage rec {
  version = "336482";
  name = "artiq-${version}";
  src = ./..;
  buildInputs = with python3Packages; [ lit outputcheck ];
  propagatedBuildInputs = with python3Packages; [ llvm-or1k llvmlite levenshtein pyqtgraph-qt5 aiohttp pygit2 pythonparser numpy dateutil quamash scipy prettytable pyserial asyncserial h5py cython regex qt5Full pyqt5 ];
  doCheck = false;
  meta = with stdenv.lib; {
    description = "";
    homepage = https://m-labs/artiq;
    license = licenses.lgpl3;
    maintainers = [ maintainers.sjmackenzie ];
    platforms = [ "x86_64-linux" ];
  };
}

