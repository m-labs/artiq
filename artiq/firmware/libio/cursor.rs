use {Read, Write};

#[derive(Debug, Clone)]
pub struct Cursor<T> {
    inner: T,
    pos:   usize
}

impl<T> Cursor<T> {
    #[inline]
    pub fn new(inner: T) -> Cursor<T> {
        Cursor { inner, pos: 0 }
    }

    #[inline]
    pub fn into_inner(self) -> T {
        self.inner
    }

    #[inline]
    pub fn get_ref(&self) -> &T {
        &self.inner
    }

    #[inline]
    pub fn get_mut(&mut self) -> &mut T {
        &mut self.inner
    }

    #[inline]
    pub fn position(&self) -> usize {
        self.pos
    }

    #[inline]
    pub fn set_position(&mut self, pos: usize) {
        self.pos = pos
    }
}

impl<T: AsRef<[u8]>> Read for Cursor<T> {
    type ReadError = !;

    fn read(&mut self, buf: &mut [u8]) -> Result<usize, Self::ReadError> {
        let data = &self.inner.as_ref()[self.pos..];
        let len = buf.len().min(data.len());
        buf[..len].copy_from_slice(&data[..len]);
        self.pos += len;
        Ok(len)
    }
}

impl<'a> Write for Cursor<&'a mut [u8]> {
    type WriteError = !;
    type FlushError = !;

    fn write(&mut self, buf: &[u8]) -> Result<usize, Self::WriteError> {
        let data = &mut self.inner[self.pos..];
        let len  = buf.len().min(data.len());
        data[..len].copy_from_slice(&buf[..len]);
        self.pos += len;
        Ok(len)
    }

    #[inline]
    fn flush(&mut self) -> Result<(), Self::FlushError> {
        Ok(())
    }
}

#[cfg(feature = "alloc")]
impl Write for Cursor<::alloc::Vec<u8>> {
    type WriteError = !;
    type FlushError = !;

    #[inline]
    fn write(&mut self, buf: &[u8]) -> Result<usize, Self::WriteError> {
        self.inner.extend_from_slice(buf);
        Ok(buf.len())
    }

    #[inline]
    fn flush(&mut self) -> Result<(), Self::FlushError> {
        Ok(())
    }
}
