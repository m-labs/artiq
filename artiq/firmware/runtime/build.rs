extern crate build_artiq;

fn main() {
    build_artiq::git_describe();
    build_artiq::misoc_cfg();
}
