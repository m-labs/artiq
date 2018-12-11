let 
  pkgs = import <nixpkgs> {};
  artiqpkgs = import ./default.nix { inherit pkgs; };
in
  pkgs.mkShell {
    # with this configuration we can't build kasli target(s) because misoc packaged via nix does not work correctly
    # want to build using nix-shell anyway? easy:
    # 1. remove misoc from the list below
    # 2. nix-shell
    # 3. export PYTHONPATH=$PYTHONPATH:/home/joachim/Desktop/projects/artiq-toolchain/misoc
    # 4. cd artiq/gateware/targets
    # 5. python kasli.py --no-compile-gateware
    buildInputs = with artiqpkgs; [ rustc cargo binutils-or1k llvm-or1k llvmlite migen misoc ] 
      ++ (with pkgs; [ python3 python36Packages.jinja2 python36Packages.numpy ]); # for artiq the python lib...
    shellHook = ''
      export TARGET_AR=${artiqpkgs.binutils-or1k}/bin/or1k-linux-ar
      export PYTHONPATH=$PYTHONPATH:`pwd`/..

      echo "please see comments in nix/shell.nix and nix/pkgs/python3Packages.nix (nixcloud team)"
    '';
  }
