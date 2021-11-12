extern crate build_misoc;
extern crate cc;

use std::path::Path;

fn main() {
    build_misoc::cfg();

    let vectors_path = "riscv32/vectors.S";

    println!("cargo:rerun-if-changed={}", vectors_path);
    cc::Build::new()
        .flag("--target=riscv32-unknown-elf")
        .file(Path::new(vectors_path))
        .compile("vectors");
}
