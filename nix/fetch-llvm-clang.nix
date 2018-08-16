{ runCommand, fetchFromGitHub, git }:

let
llvm-src = fetchFromGitHub {
  rev = "527aa86b578da5dfb9cf4510b71f0f46a11249f7";
  owner = "m-labs";
  repo = "llvm-or1k";
  sha256 = "0lmcg9xj66pf4mb6racipw67vm8kwm84dl861hyqnywd61kvhrwa";
};
clang-src = fetchFromGitHub {
  rev = "9e996136d52ed506ed8f57ef8b13b0f0f735e6a3";
  owner = "m-labs";
  repo = "clang-or1k";
  sha256 = "0w5f450i76y162aswi2c7jip8x3arzljaxhbqp8qfdffm0rdbjp4";
};
in
runCommand "llvm_or1k_src" {}''
mkdir -p $out
mkdir -p $out/tools/clang
cp -r ${llvm-src}/* $out/
cp -r ${clang-src}/* $out/tools/clang
''
