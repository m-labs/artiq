extern crate artiq_build;

fn main() {
    artiq_build::git_describe();
    artiq_build::misoc_registers();
}
