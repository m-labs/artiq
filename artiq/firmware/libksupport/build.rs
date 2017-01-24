extern crate build_artiq;

fn main() {
    build_artiq::misoc_registers();
    println!("cargo:rustc-cfg={}", "ksupport");
}
