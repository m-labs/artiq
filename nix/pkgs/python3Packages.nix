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
    
    src = fetchFromGitHub {
      owner = "m-labs";
      repo = "misoc";
      rev = "714ea6899b038c07b5a20f02a2172496486f9ef0";
      sha256 = "11cx0p41xajgpvzg1nrhkzdw0pp8jnsci37bkrzansnp1m7vmqn6";
      fetchSubmodules = true;
    };

    # test fails with:
    # NameError: name 'Module' is not defined
    # not sure if we can fix that (nixcloud team)
    #doCheck = false;
    
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
