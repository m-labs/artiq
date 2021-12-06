use riscv::register::{pmpaddr0, pmpaddr1, pmpaddr2, pmpaddr3, pmpcfg0};

static mut THREAD_DEPTH: u8 = 0;

const PMP_L    : usize = 0b10000000;
const PMP_NAPOT: usize = 0b00011000;
const PMP_X    : usize = 0b00000100;
const PMP_W    : usize = 0b00000010;
const PMP_R    : usize = 0b00000001;
const PMP_OFF  : usize = 0b00000000;

#[inline(always)]
pub unsafe fn init_stack_guard(guard_base: usize) {
    pmpaddr2::write((guard_base >> 2) | ((0x1000 - 1) >> 3));
    pmpcfg0::write((PMP_L | PMP_NAPOT) << 16);
}

#[inline(always)]
pub fn enable_user_memory() {
    pmpaddr3::write((0x80000000 - 1) >> 3);
    pmpcfg0::write((PMP_L | PMP_NAPOT | PMP_X | PMP_W | PMP_R) << 24);
}

#[inline(always)]
pub unsafe fn push_pmp_region(addr: usize) {
    let pmp_addr = (addr >> 2) | ((0x1000 - 1) >> 3);
    match THREAD_DEPTH {
        // Activate PMP0 when switching from main stack to thread
        0 => {
            pmpaddr0::write(pmp_addr);
            pmpcfg0::write(PMP_NAPOT);
        }

        // Temporarily activate PMP1 when spawning a thread from a thread
        // The thread should swap back to the main stack very soon after init
        1 => {
            pmpaddr1::write(pmp_addr);
            pmpcfg0::write(PMP_NAPOT << 8 | PMP_NAPOT);
        }

        // Thread *running* another thread should not be possible
        _ => unreachable!()
    }
    THREAD_DEPTH += 1;
}

#[inline(always)]
pub unsafe fn pop_pmp_region() {
    THREAD_DEPTH -= 1;
    match THREAD_DEPTH {
        0 => pmpcfg0::write(PMP_OFF),
        1 => pmpcfg0::write(PMP_NAPOT),
        _ => unreachable!()
    }
}
