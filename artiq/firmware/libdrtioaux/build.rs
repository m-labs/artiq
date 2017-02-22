use std::env;
use std::path::Path;
use std::io::{BufRead, BufReader};
use std::fs::File;

fn main() {
    let out_dir = env::var("BUILDINC_DIRECTORY").unwrap();
    let cfg_path = Path::new(&out_dir).join("generated").join("rust-cfg");
    println!("cargo:rerun-if-changed={}", cfg_path.to_str().unwrap());

    let f = BufReader::new(File::open(&cfg_path).unwrap());
    for line in f.lines() {
        println!("cargo:rustc-cfg={}", line.unwrap());
    }
}
