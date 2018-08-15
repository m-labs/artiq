{ runCommand, fetchFromGitHub, git }:

let
llvm-src = fetchFromGitHub {
  rev = "527aa86b578da5dfb9cf4510b71f0f46a11249f7";
  owner = "m-labs";
  repo = "llvm-or1k";
  sha256 = "0lmcg9xj66pf4mb6racipw67vm8kwm84dl861hyqnywd61kvhrwa";
};
in
runCommand "llvm_or1k_src" {}''
mkdir -p $out
cp -r ${llvm-src}/* $out/
''
