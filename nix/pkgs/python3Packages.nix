{ pkgs, stdenv, fetchFromGitHub, python, python3Packages }:

rec { 
  asyncserial = python3Packages.buildPythonPackage rec {
    version = "git-09a9fc";
    pname = "asyncserial";
    name = "${pname}-${version}";

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
      homepage    = "https://m-labs.hk/gateware.html";
      license     = licenses.bsd2;
      platforms   = platforms.unix;
    };
  };
  misoc = python3Packages.buildPythonPackage rec {
    version = "git-714ea6";
    pname = "misoc";
    name = "${pname}-${version}";
    
    # you can use the src definition to point to your local git checkout (don't forget the submodules) so
    # hacking is easier!
    #src = /home/bar/misoc;

    # instead of this (nixcloud team)
    src = fetchFromGitHub {
      owner = "m-labs";
      repo = "misoc";
      rev = "308b4728bdb1900fe3c9d71c10cc84322ad3e4ed";
      sha256 = "0fc1axrwjhb86m2dwkj6h3qwwci9xw0jsvg8pzb2r8hci2v8432h";
      fetchSubmodules = true;
    };

    # there are still so many tests failing (nixcloud team)
    # ======================================================================
    # ERROR: framebuffer (unittest.loader._FailedTest)
    # ----------------------------------------------------------------------
    # ImportError: Failed to import test module: framebuffer
    # Traceback (most recent call last):
    #   File "/nix/store/bwfygfcdvis9wd1c1v51xwnwhw1hx0a0-python3-3.6.6/lib/python3.6/unittest/loader.py", line 153, in loadTestsFromName
    #     module = __import__(module_name)
    #   File "/build/source/misoc/cores/framebuffer/__init__.py", line 1, in <module>
    #     from misoc.cores.framebuffer.core import Framebuffer
    #   File "/build/source/misoc/cores/framebuffer/core.py", line 2, in <module>
    #     from migen.flow.network import *
    # ModuleNotFoundError: No module named 'migen.flow'
    #
    #
    # watch for these messages:
    #    writing manifest file 'misoc.egg-info/SOURCES.txt'
    #    running build_ext
    #    /nix/store/w7cmmmzafv81wwhkadpar6vdvbqphzdf-python3.6-bootstrapped-pip-18.1/lib/python3.6/site-packages/setuptools/dist.py:398: UserWarning: Normalizing '0.6.dev' to '0.6.dev0'
    #      normalized_version,
    #    debug (unittest.loader._FailedTest)
    #    Run the test without collecting errors in a TestResult ... ERROR
    #    framebuffer (unittest.loader._FailedTest) ... ERROR
    #    sdram_model (unittest.loader._FailedTest) ... ERROR
    #    test (unittest.loader._FailedTest) ... ERROR
    #    test_df (unittest.loader._FailedTest) ... ERROR
    #    test_wb (unittest.loader._FailedTest) ... ERROR
    #    test_refresher (unittest.loader._FailedTest) ... ERROR
    #    test_common (unittest.loader._FailedTest) ... ERROR
    #    test_lasmi (unittest.loader._FailedTest) ... ERROR
    #    test_bankmachine (unittest.loader._FailedTest) ... ERROR
    #
    # you can disable the tests (which is a bad idea, fix them instead)
    # doCheck = false;
    
    propagatedBuildInputs = with python3Packages; [ pyserial jinja2 numpy asyncserial migen ];

    meta = with stdenv.lib; {
      description = "A high performance and small footprint system-on-chip based on Migen https://m-labs.hk";
      homepage    = "https://m-labs.hk/gateware.html";
      license     = licenses.bsd2;
      platforms   = platforms.unix;
    };
  };
  migen = python3Packages.buildPythonPackage rec {
    version = "git-3d8a58";
    pname = "migen";
    name = "${pname}-${version}";

    src = fetchFromGitHub {
      owner = "m-labs";
      repo = "migen";
      rev = "3d8a58033ea0e90e435db0d14c25c86ee7d2fee2";
      sha256 = "0fw70bzang79wylwsw9b47vssjnhx6mwzm00dg3b49iyg57jymvh";
      fetchSubmodules = true;
    };

    # FileNotFoundError: [Errno 2] No such file or directory: '/usr/local/diamond' (nixcloud team)
    doCheck = false;

    propagatedBuildInputs = with python3Packages; [ colorama sphinx sphinx_rtd_theme ] ++ (with pkgs; [ verilator ]);

    meta = with stdenv.lib; {
      description = "A Python toolbox for building complex digital hardware";
      homepage    = "https://m-labs.hk/gateware.html";
      license     = licenses.bsd2;
      platforms   = platforms.unix;
    };
  };
}
