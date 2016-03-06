{ runCommand, fetchFromGitHub, git }:

let
llvm-src = fetchFromGitHub {
  rev = "ff2fe8c318eb7c934a2f2ac8da61a00d62becf1f";
  owner = "openrisc";
  repo = "llvm-or1k";
  sha256 = "061pvc4z5i92s1xwz9ir6yqnk5vb0xd8cs9php4yy01dyvpblql7";
};
clang-src = fetchFromGitHub {
  rev = "030259ccc14261d02163cce28adb0c11243d0a99";
  owner = "openrisc";
  repo = "clang-or1k";
  sha256 = "1w7dk469svskr1c7ywcl9xsxbnvl40c28nffivpclijcvsh43463";
};
in
runCommand "llvm_or1k_src" {}''
mkdir -p $out
mkdir -p $out/tools/clang
cp -r ${llvm-src}/* $out/
cp -r ${clang-src}/* $out/tools/clang
''
