{ stdenv, git, fetchFromGitHub, fetchsvn, python3Packages, qt5Full, binutils-or1k, llvm-or1k, llvmlite, python3 }:

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
    rev = "5b391fe86f43bb9f4f96c5bc0532e2a112db2936";
    sha256 = "1gw1fk4y2l6bwq0fg2a9dfc1rvq8cv492dyil96amjdhsxvnx35b";
  };
  propagatedBuildInputs = with python3Packages; [ regex ];
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

quamash = python3Packages.buildPythonPackage rec {
  name = "quamash";
  src = fetchFromGitHub {
    owner = "harvimt";
    repo = "quamash";
    rev = "e513b30f137415c5e098602fa383e45debab85e7";
    sha256 = "117rp9r4lz0kfz4dmmpa35hp6nhbh6b4xq0jmgvqm68g9hwdxmqa";
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

in

python3Packages.buildPythonPackage rec {
  name = "artiq";
  src = ./../..;
  buildInputs = [ git ];
  propagatedBuildInputs = with python3Packages; [ binutils-or1k llvm-or1k llvmlite levenshtein pyqtgraph-qt5 aiohttp pygit2 pythonparser numpy dateutil quamash scipy prettytable pyserial asyncserial h5py cython regex qt5Full pyqt5 ];
  checkPhase = "python -m unittest discover -v artiq.test";
  meta = with stdenv.lib; {
    description = "A leading-edge control system for quantum information experiments";
    homepage = https://m-labs/artiq;
    license = licenses.lgpl3;
    #maintainers = [ maintainers.sb0 ];
    platforms = [ "x86_64-linux" ];
  };
}
