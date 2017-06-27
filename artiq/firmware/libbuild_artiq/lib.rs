extern crate walkdir;

use std::env;
use std::fs::File;
use std::io::{Write, BufRead, BufReader};
use std::path::Path;
use std::process::Command;

use walkdir::WalkDir;

pub fn git_describe() {
    let id =
        Command::new("git")
                .arg("describe")
                .arg("--tags")
                .arg("--dirty")
                .arg("--always")
                .arg("--long")
                .arg("--abbrev=8")
                .output()
                .ok()
                .and_then(|o| String::from_utf8(o.stdout).ok())
                .map(|mut s| {
                    let len = s.trim_right().len();
                    s.truncate(len);
                    s
                })
                .unwrap();
    let id = id.split("-").collect::<Vec<_>>();
    let id = format!("{}+{}.{}", id[0], id[1], id[2]);

    let out_dir = env::var("OUT_DIR").unwrap();
    let dest_path = Path::new(&out_dir).join("git-describe");
    let mut f = File::create(&dest_path).unwrap();
    f.write(id.as_bytes()).unwrap();

    println!("cargo:rust-cfg=git_describe={:?}", id);

    println!("cargo:rerun-if-changed=../../../.git/HEAD");
    for entry in WalkDir::new("../../../.git/refs") {
        let entry = entry.unwrap();
        println!("cargo:rerun-if-changed={}", entry.path().display());
    }
}

pub fn misoc_cfg() {
    let out_dir = env::var("BUILDINC_DIRECTORY").unwrap();
    let cfg_path = Path::new(&out_dir).join("generated").join("rust-cfg");
    println!("cargo:rerun-if-changed={}", cfg_path.to_str().unwrap());

    let f = BufReader::new(File::open(&cfg_path).unwrap());
    for line in f.lines() {
        println!("cargo:rustc-cfg={}", line.unwrap());
    }
}
