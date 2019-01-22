{ pkgs, stdenv, fetchFromGitHub, python, python3Packages }:

rec { 
  asyncserial = python3Packages.buildPythonPackage rec {
    name = "asyncserial";

    src = fetchFromGitHub {
      owner = "m-labs";
      repo = "asyncserial";
      rev = "d95bc1d6c791b0e9785935d2f62f628eb5cdf98d";
      sha256 = "0yzkka9jk3612v8gx748x6ziwykq5lr7zmr9wzkcls0v2yilqx9k";
      fetchSubmodules = true;
    };

    propagatedBuildInputs = with python3Packages; [ pyserial ] ++ (with pkgs; [ ]);

    meta = with stdenv.lib; {
      description = "asyncio support for pyserial";
      homepage    = "https://m-labs.hk";
      license     = licenses.bsd2;
      platforms   = platforms.unix;
    };
  };
  misoc = python3Packages.buildPythonPackage rec {
    name = "misoc";
    
    src = fetchFromGitHub {
      owner = "m-labs";
      repo = "misoc";
      rev = "308b4728bdb1900fe3c9d71c10cc84322ad3e4ed";
      sha256 = "0fc1axrwjhb86m2dwkj6h3qwwci9xw0jsvg8pzb2r8hci2v8432h";
      fetchSubmodules = true;
    };

    # TODO: fix misoc bitrot and re-enable tests
    doCheck = false;
    
    propagatedBuildInputs = with python3Packages; [ pyserial jinja2 numpy asyncserial migen ];

    meta = with stdenv.lib; {
      description = "A high performance and small footprint system-on-chip based on Migen";
      homepage    = "https://m-labs.hk/migen";
      license     = licenses.bsd2;
      platforms   = platforms.unix;
    };
  };
  migen = python3Packages.buildPythonPackage rec {
    name = "migen";

    src = fetchFromGitHub {
      owner = "m-labs";
      repo = "migen";
      rev = "3d8a58033ea0e90e435db0d14c25c86ee7d2fee2";
      sha256 = "0fw70bzang79wylwsw9b47vssjnhx6mwzm00dg3b49iyg57jymvh";
      fetchSubmodules = true;
    };

    # TODO: fix migen platform issues and re-enable tests
    doCheck = false;

    propagatedBuildInputs = with python3Packages; [ colorama sphinx sphinx_rtd_theme ] ++ (with pkgs; [ verilator ]);

    meta = with stdenv.lib; {
      description = "A Python toolbox for building complex digital hardware";
      homepage    = "https://m-labs.hk/migen";
      license     = licenses.bsd2;
      platforms   = platforms.unix;
    };
  };
  microscope = python3Packages.buildPythonPackage rec {
    name = "microscope";

    src = fetchFromGitHub {
      owner = "m-labs";
      repo = "microscope";
      rev = "02cffc360ec5a234c589de6cb9616b057ed22253";
      sha256 = "09yvgk16xfv5r5cf55vcg0f14wam42w53r4snlalcyw5gkm0rlhq";
    };

    propagatedBuildInputs = with python3Packages; [ pyserial prettytable msgpack-python migen ];

    meta = with stdenv.lib; {
      description = "Finding the bacteria in rotting FPGA designs";
      homepage    = "https://m-labs.hk/migen";
      license     = licenses.bsd2;
      platforms   = platforms.unix;
    };
  };
  jesd204b = python3Packages.buildPythonPackage rec {
    name = "jesd204b";

    src = fetchFromGitHub {
      owner = "m-labs";
      repo = "jesd204b";
      rev = "03d3280690727b12b6522cbd294138e66dd157c9";
      sha256 = "1hpx4y8ynhsmwsq4ry748q6bkh8jvv2hy8b7hifxjmlh174y8rb0";
    };

    propagatedBuildInputs = with python3Packages; [ migen misoc ];

    meta = with stdenv.lib; {
      description = "JESD204B core for Migen/MiSoC";
      homepage    = "https://m-labs.hk/migen";
      license     = licenses.bsd2;
      platforms   = platforms.unix;
    };
  };
}
