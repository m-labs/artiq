extern crate build_misoc;

fn main() {
    build_misoc::cfg();
    println!("cargo:rustc-cfg={}", "ksupport");
}
