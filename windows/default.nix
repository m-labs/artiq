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
in {
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
}
