use std::io::{self, Read};
use logger_artiq::BufferLogger;
use sched::Io;
use sched::{TcpListener, TcpStream};
use board;
use mgmt_proto::*;

fn check_magic(stream: &mut TcpStream) -> io::Result<()> {
    const MAGIC: &'static [u8] = b"ARTIQ management\n";

    let mut magic: [u8; 17] = [0; 17];
    stream.read_exact(&mut magic)?;
    if magic != MAGIC {
        Err(io::Error::new(io::ErrorKind::InvalidData, "unrecognized magic"))
    } else {
        Ok(())
    }
}

fn worker(mut stream: &mut TcpStream) -> io::Result<()> {
    check_magic(&mut stream)?;
    info!("new connection from {}", stream.remote_endpoint());

    loop {
        match Request::read_from(stream)? {
            Request::GetLog => {
                BufferLogger::with_instance(|logger| {
                    logger.extract(|log| {
                        Reply::LogContent(log).write_to(stream)
                    })
                })?;
            },

            Request::ClearLog => {
                BufferLogger::with_instance(|logger|
                    logger.clear());
                Reply::Success.write_to(stream)?;
            },

            Request::SetLogFilter(level) => {
                info!("changing log level to {}", level);
                BufferLogger::with_instance(|logger|
                    logger.set_max_log_level(level));
                Reply::Success.write_to(stream)?;
            },

            Request::SetUartLogFilter(level) => {
                info!("changing UART log level to {}", level);
                BufferLogger::with_instance(|logger|
                    logger.set_uart_log_level(level));
                Reply::Success.write_to(stream)?;
            },

            Request::Hotswap(firmware) => {
                Reply::RebootImminent.write_to(stream)?;
                stream.close()?;
                warn!("hotswapping firmware");
                unsafe { board::boot::hotswap(&firmware) }
            },

            Request::Reboot => {
                Reply::RebootImminent.write_to(stream)?;
                stream.close()?;
                warn!("rebooting");
                unsafe { board::boot::reboot() }
            }
        };
    }
}

pub fn thread(io: Io) {
    let listener = TcpListener::new(&io, 4096);
    listener.listen(1380).expect("mgmt: cannot listen");
    info!("management interface active");

    loop {
        let stream = listener.accept().expect("mgmt: cannot accept").into_handle();
        io.spawn(4096, move |io| {
            let mut stream = TcpStream::from_handle(&io, stream);
            match worker(&mut stream) {
                Ok(()) => {},
                Err(err) => error!("aborted: {}", err)
            }
        });
    }
}
