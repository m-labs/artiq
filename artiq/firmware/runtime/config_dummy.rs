pub fn read<F: FnOnce(Result<&[u8], ()>) -> R, R>(_key: &str, f: F) -> R {
    f(Err(()))
}

pub fn read_str<F: FnOnce(Result<&str, ()>) -> R, R>(_key: &str, f: F) -> R {
    f(Err(()))
}

pub fn write(_key: &str, _value: &[u8]) -> Result<(), ()> {
    Err(())
}

pub fn remove(_key: &str) -> Result<(), ()> {
    Err(())
}

pub fn erase() -> Result<(), ()> {
    Err(())
}
