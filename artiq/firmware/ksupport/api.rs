use board_misoc::csr;

macro_rules! api {
    ($i:ident) => ({
        extern { static $i: u8; }
        api!($i = &$i as *const _)
    });
    ($i:ident, $d:item) => ({
        $d
        api!($i = $i)
    });
    ($i:ident = $e:expr) => {
        (stringify!($i), unsafe { $e as *const () })
    }
}

pub fn resolve(required: &[u8]) -> Option<u32> {
    unsafe {
        API.iter()
           .find(|&&(exported, _)| exported.as_bytes() == required)
           .map(|&(_, ptr)| ptr as u32)
    }
}

#[allow(unused_unsafe)]
static mut API: &'static [(&'static str, *const ())] = &[
    api!(__divsi3),
    api!(__modsi3),
    api!(__ledf2),
    api!(__gedf2),
    api!(__unorddf2),
    api!(__eqdf2),
    api!(__ltdf2),
    api!(__nedf2),
    api!(__gtdf2),
    api!(__addsf3),
    api!(__subsf3),
    api!(__mulsf3),
    api!(__divsf3),
    api!(__lshrdi3),
    api!(__muldi3),
    api!(__divdi3),
    api!(__ashldi3),
    api!(__ashrdi3),
    api!(__udivmoddi4),
    api!(__floatsisf),
    api!(__floatunsisf),
    api!(__fixsfsi),
    api!(__fixunssfsi),
    api!(__adddf3),
    api!(__subdf3),
    api!(__muldf3),
    api!(__divdf3),
    api!(__floatsidf),
    api!(__floatunsidf),
    api!(__floatdidf),
    api!(__fixdfsi),
    api!(__fixdfdi),
    api!(__fixunsdfsi),
    api!(__udivdi3),
    api!(__umoddi3),
    api!(__moddi3),
    api!(__powidf2),

    /* libc */
    api!(memcpy, extern { fn memcpy(dest: *mut u8, src: *const u8, n: usize) -> *mut u8; }),
    api!(memmove, extern { fn memmove(dest: *mut u8, src: *const u8, n: usize) -> *mut u8; }),
    api!(memset, extern { fn memset(s: *mut u8, c: i32, n: usize) -> *mut u8; }),
    api!(memcmp, extern { fn memcmp(s1: *const u8, s2: *const u8, n: usize) -> i32; }),

    /* libm */
    // commented out functions are not available with the libm used here, but are available in NAR3.
    api!(acos),
    api!(acosh),
    api!(asin),
    api!(asinh),
    api!(atan),
    api!(atan2),
    api!(atanh),
    api!(cbrt),
    api!(ceil),
    api!(copysign),
    api!(cos),
    api!(cosh),
    api!(erf),
    api!(erfc),
    api!(exp),
    //api!(exp2),
    //api!(exp10),
    api!(expm1),
    api!(fabs),
    api!(floor),
    // api!(fmax),
    // api!(fmin),
    //api!(fma),
    api!(fmod),
    api!(hypot),
    api!(j0),
    api!(j1),
    api!(jn),
    api!(lgamma),
    api!(log),
    //api!(log2),
    api!(log10),
    api!(nextafter),
    api!(pow),
    api!(round),
    api!(sin),
    api!(sinh),
    api!(sqrt),
    api!(tan),
    api!(tanh),
    //api!(tgamma),
    //api!(trunc),
    api!(y0),
    api!(y1),
    api!(yn),

    /* exceptions */
    api!(_Unwind_Resume = ::unwind::_Unwind_Resume),
    api!(__nac3_personality = ::eh_artiq::personality),
    api!(__nac3_raise = ::eh_artiq::raise),
    api!(__nac3_resume = ::eh_artiq::resume),
    api!(__nac3_end_catch = ::eh_artiq::end_catch),
    /* legacy exception symbols */
    api!(__artiq_personality = ::eh_artiq::personality),
    api!(__artiq_raise = ::eh_artiq::raise),
    api!(__artiq_resume = ::eh_artiq::resume),
    api!(__artiq_end_catch = ::eh_artiq::end_catch),

    /* proxified syscalls */
    api!(core_log),

    api!(now = csr::rtio::NOW_HI_ADDR as *const _),

    api!(rpc_send = ::rpc_send),
    api!(rpc_send_async = ::rpc_send_async),
    api!(rpc_recv = ::rpc_recv),

    api!(cache_get = ::cache_get),
    api!(cache_put = ::cache_put),

    /* direct syscalls */
    api!(rtio_init = ::rtio::init),
    api!(rtio_get_destination_status = ::rtio::get_destination_status),
    api!(rtio_get_counter = ::rtio::get_counter),
    api!(rtio_log),
    api!(rtio_output = ::rtio::output),
    api!(rtio_output_wide = ::rtio::output_wide),
    api!(rtio_input_timestamp = ::rtio::input_timestamp),
    api!(rtio_input_data = ::rtio::input_data),
    api!(rtio_input_timestamped_data = ::rtio::input_timestamped_data),

    api!(dma_record_start = ::dma_record_start),
    api!(dma_record_stop = ::dma_record_stop),
    api!(dma_erase = ::dma_erase),
    api!(dma_retrieve = ::dma_retrieve),
    api!(dma_playback = ::dma_playback),

    api!(i2c_start = ::nrt_bus::i2c::start),
    api!(i2c_restart = ::nrt_bus::i2c::restart),
    api!(i2c_stop = ::nrt_bus::i2c::stop),
    api!(i2c_write = ::nrt_bus::i2c::write),
    api!(i2c_read = ::nrt_bus::i2c::read),
    api!(i2c_switch_select = ::nrt_bus::i2c::switch_select),

    api!(spi_set_config = ::nrt_bus::spi::set_config),
    api!(spi_write = ::nrt_bus::spi::write),
    api!(spi_read = ::nrt_bus::spi::read),
];
