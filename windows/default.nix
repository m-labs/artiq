{ sipyco, nac3, artiq-comtools, artiq }:
let
  pkgs = import nac3.inputs.nixpkgs { system = "x86_64-linux"; };
  makeMsys2 = { name, version, src }: pkgs.stdenvNoCC.mkDerivation {
    pname = "${name}-msys2-pkg";
    inherit version;
    nativeBuildInputs = [
      pkgs.pacman pkgs.fakeroot pkgs.libarchive pkgs.zstd pkgs.file
      nac3.packages.x86_64-w64-mingw32.wine-msys2-build
    ];
    inherit src;
    phases = [ "buildPhase" "installPhase" ];
    buildPhase =
      ''
      export DRV_VERSION=${version}
      ln -s ${./PKGBUILD.${name}} PKGBUILD
      ln -s ${./PKGBUILD.common} PKGBUILD.common
      ln -s $src source
      tar cfh source.tar source
      rm source
      makepkg --config ${./makepkg.conf} --nodeps
      '';
    installPhase =
      ''
      mkdir $out $out/nix-support
      cp *.pkg.tar.zst $out
      echo file msys2 $out/*.pkg.tar.zst >> $out/nix-support/hydra-build-products
      '';
  };
in rec {
  qasync-pkg = makeMsys2 {
    name = "qasync";
    src = artiq.packages.x86_64-linux.qasync.src;
    inherit (artiq.packages.x86_64-linux.qasync) version;
  };
  pyqtgraph-pkg = makeMsys2 {
    name = "pyqtgraph";
    src = pkgs.python3Packages.pyqtgraph.src;
    inherit (pkgs.python3Packages.pyqtgraph) version;
  };
  sipyco-pkg = makeMsys2 {
    name = "sipyco";
    src = sipyco;
    inherit (sipyco.packages.x86_64-linux.sipyco) version;
  };
  artiq-comtools-pkg = makeMsys2 {
    name = "artiq-comtools";
    src = artiq-comtools;
    inherit (artiq-comtools.packages.x86_64-linux.artiq-comtools) version;
  };
  artiq-pkg = makeMsys2 {
    name = "artiq";
    src = artiq;
    inherit (artiq.packages.x86_64-linux.artiq) version;
  };
  msys2-repos = pkgs.stdenvNoCC.mkDerivation {
    name = "msys2-repos";
    nativeBuildInputs = [ pkgs.pacman ];
    phases = [ "buildPhase" ];
    buildPhase =
      ''
      mkdir $out
      cd $out
      ln -s ${qasync-pkg}/*.pkg.tar.zst .
      ln -s ${pyqtgraph-pkg}/*.pkg.tar.zst .
      ln -s ${sipyco-pkg}/*.pkg.tar.zst .
      ln -s ${artiq-comtools-pkg}/*.pkg.tar.zst .
      ln -s ${nac3.packages.x86_64-w64-mingw32.nac3artiq-pkg}/*.pkg.tar.zst .
      ln -s ${artiq-pkg}/*.pkg.tar.zst .
      repo-add artiq.db.tar.gz *.pkg.tar.zst
      '';
  };
}
