{ stdenv, fetchFromGitHub, fetchsvn, python35Packages, qt5Full, llvm-or1k, llvmlite, python35}:

let

levenshtein = python35Packages.buildPythonPackage rec {
  name = "levenshtein";
  src = fetchFromGitHub {
    owner = "ztane";
    repo = "python-Levenshtein";
    rev = "854e61a05bb8b750e990add96df412cd5448b75e";
    sha256 = "1yf21kg1g2ivm5a4dx1jra9k0c33np54d0hk5ymnfyc4f6pg386q";
  };
  doCheck = false;
};

sphinx-argparse = python35Packages.buildPythonPackage rec {
  name = "sphinx-argparse";
  src = fetchFromGitHub {
    owner = "ribozz";
    repo = "sphinx-argparse";
    rev = "cc95938b8fbf870f7a5c012d4d84a29cfbac5e06";
    sha256 = "1rsjlsnrpd4i4zx2sylilf6lfi77k0fclbhilrgx1m53ixllwg38";
  };
  buildInputs = with python35Packages; [ sphinx ];
  doCheck = false;
};

pythonparser = python35Packages.buildPythonPackage rec {
  name = "pythonparser";
  src = fetchFromGitHub {
    owner = "m-labs";
    repo = "pythonparser";
    rev = "8bdc7badbd08e2196b864e12889ea9191ca6e09c";
    sha256 = "1f538wnjlqah0dsvq256k2rv7s7bffsvjcxy8fq0x3a4g0s6pm9d";
  };
  buildInputs = with python35Packages; [ regex ];
  doCheck = false;
};

ml-pyserial = python35Packages.buildPythonPackage rec {
  name = "pyserial";
  src = fetchFromGitHub {
    owner = "m-labs";
    repo = "pyserial";
    rev = "f30653b23f01c1cc27eb9731afc8ad66a723a4c0";
    sha256 = "18xwsmpklggrm07b17ficpyjxnfgpw0k9lbz44nq4iflr8gmf33f";
  };
  buildInputs = with python35Packages; [ regex ];
  doCheck = false;
};

pyqtgraph = python35Packages.buildPythonPackage rec {
  name = "pyqtgraph";
  src = fetchFromGitHub {
    owner = "m-labs";
    repo = "pyqtgraph";
    rev = "8e9ee6fd3cabcc06d25cde5f13921e5d9d11c588";
    sha256 = "0ynhsd4nlbz4pgwch0w767a9ybazn5f33rakpjdrcwldvrrrng6y";
  };
  buildInputs = with python35Packages; [ numpy ];
  doCheck = false;
};

outputcheck = python35Packages.buildPythonPackage rec {
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

quamash = python35Packages.buildPythonPackage rec {
  name = "quamash";
  src = fetchFromGitHub {
    owner = "harvimt";
    repo = "quamash";
    rev = "bbab9e30e10b71a95687b03a93524173fb7b43f0";
    sha256 = "08hp2q4ifj6z2ww05c7zsy0cd732k9rnaims1j43vr4hhxx950mk";
  };
  buildInputs = with python35Packages; [ pyqt5 ];
  doCheck = false;
};

lit = python35Packages.buildPythonPackage rec {
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

python35Packages.buildPythonPackage rec {
  version = "336482";
  name = "artiq-${version}";
  src = ./..;
  buildInputs = with python35Packages; [
    llvm-or1k llvmlite sphinx-argparse levenshtein
    pyqtgraph aiohttp pygit2 pythonparser numpy
    dateutil sphinx quamash scipy outputcheck
    prettytable lit ml-pyserial h5py cython regex qt5Full pyqt5 ];
  doCheck = false;
  meta = with stdenv.lib; {
    description = "";
    homepage = https://m-labs/artiq;
    license = licenses.gpl3;
    maintainers = [ maintainers.sjmackenzie ];
    platforms = [ "x86_64-linux" ];
  };
}

