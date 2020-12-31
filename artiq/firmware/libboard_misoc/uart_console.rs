use core::fmt;

pub struct Console;

impl fmt::Write for Console {
    #[cfg(has_uart)]
    fn write_str(&mut self, s: &str) -> Result<(), fmt::Error> {
        use csr;

        for c in s.bytes() {
            unsafe {
                while csr::uart::txfull_read() != 0 {}
                csr::uart::rxtx_write(c)
            }
        }

        Ok(())
    }

    #[cfg(not(has_uart))]
    fn write_str(&mut self, _s: &str) -> Result<(), fmt::Error> {
        Ok(())
    }
}

#[macro_export]
macro_rules! print {
    ($($arg:tt)*) => ({
        use core::fmt::Write;
        write!($crate::uart_console::Console, $($arg)*).unwrap()
    })
}

#[macro_export]
macro_rules! println {
    ($fmt:expr) => (print!(concat!($fmt, "\n")));
    ($fmt:expr, $($arg:tt)*) => (print!(concat!($fmt, "\n"), $($arg)*));
}
