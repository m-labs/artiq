use core::ops::Deref;
use core::fmt;
use alloc::rc::Rc;

pub struct Urc<T: ?Sized>(Rc<T>);

impl<T> Urc<T> {
    pub fn new(value: T) -> Urc<T> { Urc(Rc::new(value)) }
}

unsafe impl<T: ?Sized> Send for Urc<T> {}

unsafe impl<T: ?Sized> Sync for Urc<T> {}

impl<T: ?Sized> Deref for Urc<T> {
    type Target = T;

    fn deref(&self) -> &Self::Target { self.0.deref() }
}

impl<T: ?Sized> Clone for Urc<T> {
    fn clone(&self) -> Urc<T> {
        Urc(self.0.clone())
    }
}

impl<T: ?Sized + fmt::Debug> fmt::Debug for Urc<T> {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        fmt::Debug::fmt(&**self, f)
    }
}
