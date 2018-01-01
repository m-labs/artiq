use board::boot;
use std::io::{self, Read, Write};
use log::{self, LevelFilter};
use logger_artiq::BufferLogger;
use sched::Io;
use sched::{TcpListener, TcpStream};
use proto::WriteExt;
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

fn worker(io: &Io, stream: &mut TcpStream) -> io::Result<()> {
    check_magic(stream)?;
    info!("new connection from {}", stream.remote_endpoint());

    loop {
        match Request::read_from(stream)? {
            Request::GetLog => {
                BufferLogger::with(|logger| {
                    logger.extract(|log| {
                        Reply::LogContent(log).write_to(stream)
                    })
                })?;
            },

            Request::ClearLog => {
                BufferLogger::with(|logger|
                    logger.clear());
                Reply::Success.write_to(stream)?;
            },

            Request::PullLog => {
                loop {
                    io.until(|| BufferLogger::with(|logger| !logger.is_empty()))?;

                    BufferLogger::with(|logger| {
                        let log_level = log::max_level();
                        logger.extract(|log| {
                            stream.write_string(log)?;

                            if log_level == LevelFilter::Trace {
                                // Hold exclusive access over the logger until we get positive
                                // acknowledgement; otherwise we get an infinite loop of network
                                // trace messages being transmitted and causing more network
                                // trace messages to be emitted.
                                //
                                // Any messages unrelated to this management socket that arrive
                                // while it is flushed are lost, but such is life.
                                stream.flush()
                            } else {
                                Ok(())
                            }
                        })?;

                        Ok(logger.clear()) as io::Result<()>
                    })?;
                }
            },

            Request::SetLogFilter(level) => {
                info!("changing log level to {}", level);
                log::set_max_level(level);
                Reply::Success.write_to(stream)?;
            },

            Request::SetUartLogFilter(level) => {
                info!("changing UART log level to {}", level);
                BufferLogger::with(|logger|
                    logger.set_uart_log_level(level));
                Reply::Success.write_to(stream)?;
            },

            Request::Hotswap(firmware) => {
                warn!("hotswapping firmware");
                Reply::RebootImminent.write_to(stream)?;
                stream.close()?;
                stream.flush()?;
                unsafe { boot::hotswap(&firmware) }
            },

            Request::Reboot => {
                Reply::RebootImminent.write_to(stream)?;
                stream.close()?;
                warn!("restarting");
                unsafe { boot::reset() }
            }
        };
    }
}

pub fn thread(io: Io) {
    let listener = TcpListener::new(&io, 8192);
    listener.listen(1380).expect("mgmt: cannot listen");
    info!("management interface active");

    loop {
        let stream = listener.accept().expect("mgmt: cannot accept").into_handle();
        io.spawn(4096, move |io| {
            let mut stream = TcpStream::from_handle(&io, stream);
            match worker(&io, &mut stream) {
                Ok(()) => (),
                Err(ref err) if err.kind() == io::ErrorKind::UnexpectedEof => (),
                Err(ref err) if err.kind() == io::ErrorKind::WriteZero => (),
                Err(err) => error!("aborted: {}", err)
            }
        });
    }
}
