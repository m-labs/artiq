extern crate build_artiq;

use std::env;
use std::fs::File;
use std::io::Write;
use std::path::PathBuf;
use std::process::Command;

fn gen_hmc7043_writes() {
    println!("cargo:rerun-if-changed=hmc7043_gen_writes.py");
    println!("cargo:rerun-if-changed=hmc7043_guiexport_6gbps.py");

    let hmc7043_writes =
        Command::new("python3")
                .arg("hmc7043_gen_writes.py")
                .arg("hmc7043_guiexport_6gbps.py")
                .output()
                .ok()
                .and_then(|o| String::from_utf8(o.stdout).ok())
                .unwrap();
    let out_dir = PathBuf::from(env::var("OUT_DIR").unwrap());
    let mut f = File::create(out_dir.join("hmc7043_writes.rs")).unwrap();
    write!(f, "{}", hmc7043_writes).unwrap();
}

fn main() {
    build_artiq::misoc_cfg();
    gen_hmc7043_writes();
}
