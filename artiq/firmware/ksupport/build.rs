extern crate build_artiq;

fn main() {
    build_artiq::misoc_cfg();
    println!("cargo:rustc-cfg={}", "ksupport");
}
