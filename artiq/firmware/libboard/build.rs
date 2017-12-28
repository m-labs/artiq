extern crate build_misoc;
extern crate cc;

use std::env;
use std::path::Path;

fn main() {
    build_misoc::cfg();

    let triple = env::var("TARGET").unwrap();
    let arch = triple.split("-").next().unwrap();
    let vectors_path = Path::new(arch).join("vectors.S");

    println!("cargo:rerun-if-changed={}", vectors_path.to_str().unwrap());
    cc::Build::new()
        .file(vectors_path)
        .compile("vectors");
}
