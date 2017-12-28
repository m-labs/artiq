extern crate build_misoc;
extern crate build_artiq;

fn main() {
    build_misoc::cfg();
    build_artiq::git_describe();
}
