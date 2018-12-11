let 
  pkgs = import <nixpkgs> {};
  artiqpkgs = import ./default.nix { inherit pkgs; };
in
  pkgs.mkShell {
    buildInputs = with artiqpkgs; [ rustc cargo binutils-or1k llvm-or1k llvmlite migen misoc ] 
      ++ (with pkgs; [ python3 python36Packages.jinja2 python36Packages.numpy ]); # for artiq the python lib...
    shellHook = ''
      export TARGET_AR=${artiqpkgs.binutils-or1k}/bin/or1k-linux-ar
      export PYTHONPATH=$PYTHONPATH:`pwd`/..

      echo "hi from the nixcloud team"
    '';
  }
