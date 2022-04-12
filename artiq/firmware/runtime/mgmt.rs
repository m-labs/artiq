use log::{self, LevelFilter};

use io::{Write, ProtoWrite, Error as IoError};
use board_misoc::{config, spiflash};
use logger_artiq::BufferLogger;
use mgmt_proto::*;
use sched::{Io, TcpListener, TcpStream, Error as SchedError};

impl From<SchedError> for Error<SchedError> {
    fn from(value: SchedError) -> Error<SchedError> {
        Error::Io(IoError::Other(value))
    }
}

fn worker(io: &Io, stream: &mut TcpStream) -> Result<(), Error<SchedError>> {
    read_magic(stream)?;
    Write::write_all(stream, "e".as_bytes())?;
    info!("new connection from {}", stream.remote_endpoint());

    loop {
        match Request::read_from(stream)? {
            Request::GetLog => {
                BufferLogger::with(|logger| {
                    let mut buffer = io.until_ok(|| logger.buffer())?;
                    Reply::LogContent(buffer.extract()).write_to(stream)
                })?;
            }
            Request::ClearLog => {
                BufferLogger::with(|logger| -> Result<(), Error<SchedError>> {
                    let mut buffer = io.until_ok(|| logger.buffer())?;
                    Ok(buffer.clear())
                })?;

                Reply::Success.write_to(stream)?;
            }
            Request::PullLog => {
                BufferLogger::with(|logger| -> Result<(), Error<SchedError>> {
                    loop {
                        // Do this *before* acquiring the buffer, since that sets the log level
                        // to OFF.
                        let log_level = log::max_level();

                        let mut buffer = io.until_ok(|| logger.buffer())?;
                        if buffer.is_empty() { continue }

                        stream.write_string(buffer.extract())?;

                        if log_level == LevelFilter::Trace {
                            // Hold exclusive access over the logger until we get positive
                            // acknowledgement; otherwise we get an infinite loop of network
                            // trace messages being transmitted and causing more network
                            // trace messages to be emitted.
                            //
                            // Any messages unrelated to this management socket that arrive
                            // while it is flushed are lost, but such is life.
                            stream.flush()?;
                        }

                        // Clear the log *after* flushing the network buffers, or we're just
                        // going to resend all the trace messages on the next iteration.
                        buffer.clear();
                    }
                })?;
            }
            Request::SetLogFilter(level) => {
                info!("changing log level to {}", level);
                log::set_max_level(level);
                Reply::Success.write_to(stream)?;
            }
            Request::SetUartLogFilter(level) => {
                info!("changing UART log level to {}", level);
                BufferLogger::with(|logger|
                    logger.set_uart_log_level(level));
                Reply::Success.write_to(stream)?;
            }

            Request::ConfigRead { ref key } => {
                config::read(key, |result| {
                    match result {
                        Ok(value) => Reply::ConfigData(&value).write_to(stream),
                        Err(_)    => Reply::Error.write_to(stream)
                    }
                })?;
            }
            Request::ConfigWrite { ref key, ref value } => {
                match config::write(key, value) {
                    Ok(_)  => Reply::Success.write_to(stream),
                    Err(_) => Reply::Error.write_to(stream)
                }?;
            }
            Request::ConfigRemove { ref key } => {
                match config::remove(key) {
                    Ok(()) => Reply::Success.write_to(stream),
                    Err(_) => Reply::Error.write_to(stream)
                }?;

            }
            Request::ConfigErase => {
                match config::erase() {
                    Ok(()) => Reply::Success.write_to(stream),
                    Err(_) => Reply::Error.write_to(stream)
                }?;
            }

            Request::Reboot => {
                Reply::RebootImminent.write_to(stream)?;
                stream.close()?;
                stream.flush()?;

                warn!("restarting");
                unsafe { spiflash::reload(); }
            }

            Request::DebugAllocator =>
                unsafe { println!("{}", ::ALLOC) },
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
                Err(Error::Io(IoError::UnexpectedEnd)) => (),
                Err(err) => error!("aborted: {}", err)
            }
            stream.close().expect("mgmt: close socket");
        });
    }
}
