mod imp {
    use csr;

    pub fn reload () -> ! {
        unsafe {
            csr::icap::iprog_write(1);
        }
        loop {}
    }
}

pub use self::imp::*;
