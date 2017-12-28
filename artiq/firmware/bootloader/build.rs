extern crate build_artiq;

fn main() {
    build_artiq::misoc_cfg();
    build_artiq::git_describe();
}
