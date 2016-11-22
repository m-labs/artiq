extern crate walkdir;

use std::env;
use std::fs::File;
use std::io::Write;
use std::path::Path;
use std::process::Command;

use walkdir::WalkDir;

fn main() {
    let out_dir = env::var("OUT_DIR").unwrap();
    let dest_path = Path::new(&out_dir).join("git_info.rs");
    let mut f = File::create(&dest_path).unwrap();

    let id = git_describe().unwrap();
    let id = id.split("-").collect::<Vec<_>>();
    let id = format!("{}+{}.{}", id[0], id[1], id[2]);
    writeln!(f, "const GIT_COMMIT: &'static str = {:?};", id).unwrap();

    println!("cargo:rerun-if-changed=../../.git/HEAD");
    for entry in WalkDir::new("../../.git/refs") {
        let entry = entry.unwrap();
        println!("cargo:rerun-if-changed={}", entry.path().display());
    }
}

// Returns `None` if git is not available.
fn git_describe() -> Option<String> {
    Command::new("git")
        .arg("describe")
        .arg("--tags")
        .arg("--dirty")
        .arg("--always")
        .arg("--long")
        .output()
        .ok()
        .and_then(|o| String::from_utf8(o.stdout).ok())
        .map(|mut s| {
            let len = s.trim_right().len();
            s.truncate(len);
            s
        })
}
