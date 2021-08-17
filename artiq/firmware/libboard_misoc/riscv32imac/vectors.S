# Adapted from riscv-rt project, with the following license:
#
# Copyright 2018 RISC-V team
#
# Permission to use, copy, modify, and/or distribute this software for any purpose 
# with or without fee is hereby granted, provided that the above copyright notice and
# this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH
# REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND
# FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT,
# OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA
# OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION,
# ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

#if __riscv_xlen == 64
# define STORE    sd
# define LOAD     ld
# define LOG_REGBYTES 3
#else
# define STORE    sw
# define LOAD     lw
# define LOG_REGBYTES 2
#endif
#define REGBYTES (1 << LOG_REGBYTES)

/*
    Entry point of all programs (_reset_handler).

    It initializes DWARF call frame information, the stack pointer, the
    frame pointer (needed for closures to work in start_rust) and the global
    pointer. Then it calls _start_rust.
*/

.section .vectors, "ax", @progbits
.global _reset_handler

_reset_handler:
    /* Jump to the absolute address defined by the linker script. */
    // for 32bit
    .if __riscv_xlen == 32
    lui ra, %hi(_abs_start)
    jr %lo(_abs_start)(ra)
    .endif

    // for 64bit
    .if __riscv_xlen == 64
.option push
.option norelax // to prevent an unsupported R_RISCV_ALIGN relocation from being generated
1:
    auipc ra, %pcrel_hi(1f)
    ld ra, %pcrel_lo(1b)(ra)
    jr ra
    .align  3
1:
    .dword _abs_start
.option pop
    .endif

_abs_start:
    .cfi_startproc
    .cfi_undefined ra

    csrw mie, 0
    csrw mip, 0

    li  x1, 0
    li  x2, 0
    li  x3, 0
    li  x4, 0
    li  x5, 0
    li  x6, 0
    li  x7, 0
    li  x8, 0
    li  x9, 0
    li  x10,0
    li  x11,0
    li  x12,0
    li  x13,0
    li  x14,0
    li  x15,0
    li  x16,0
    li  x17,0
    li  x18,0
    li  x19,0
    li  x20,0
    li  x21,0
    li  x22,0
    li  x23,0
    li  x24,0
    li  x25,0
    li  x26,0
    li  x27,0
    li  x28,0
    li  x29,0
    li  x30,0
    li  x31,0

    // Check hart id
    csrr a2, mhartid

    // Allocate stacks
    la sp, _fstack

    // Set frame pointer
    add s0, sp, zero

    // Set trap vector
    la t0, _start_trap
    csrw mtvec, t0

    // Zero initialize .bss
    la t0, _fbss
    la t1, _ebss
    beq t0, t1, 2f
1:  STORE zero, 0(t0)
    addi t0, t0, REGBYTES
    bne t0, t1, 1b
2:
    // Enter main firmware
    jal zero, main

    .cfi_endproc

/*
    Trap entry point (_start_trap)

    Saves caller saved registers ra, t0..6, a0..7, calls exception,
    restores caller saved registers and then returns.
*/
.global _start_trap
/* Make it .weak so PAC/HAL can provide their own if needed. */
.weak _start_trap

_start_trap:
    addi sp, sp, -16*REGBYTES

    STORE ra, 0*REGBYTES(sp)
    STORE t0, 1*REGBYTES(sp)
    STORE t1, 2*REGBYTES(sp)
    STORE t2, 3*REGBYTES(sp)
    STORE t3, 4*REGBYTES(sp)
    STORE t4, 5*REGBYTES(sp)
    STORE t5, 6*REGBYTES(sp)
    STORE t6, 7*REGBYTES(sp)
    STORE a0, 8*REGBYTES(sp)
    STORE a1, 9*REGBYTES(sp)
    STORE a2, 10*REGBYTES(sp)
    STORE a3, 11*REGBYTES(sp)
    STORE a4, 12*REGBYTES(sp)
    STORE a5, 13*REGBYTES(sp)
    STORE a6, 14*REGBYTES(sp)
    STORE a7, 15*REGBYTES(sp)

    add a0, sp, zero
    jal ra, exception

    LOAD ra, 0*REGBYTES(sp)
    LOAD t0, 1*REGBYTES(sp)
    LOAD t1, 2*REGBYTES(sp)
    LOAD t2, 3*REGBYTES(sp)
    LOAD t3, 4*REGBYTES(sp)
    LOAD t4, 5*REGBYTES(sp)
    LOAD t5, 6*REGBYTES(sp)
    LOAD t6, 7*REGBYTES(sp)
    LOAD a0, 8*REGBYTES(sp)
    LOAD a1, 9*REGBYTES(sp)
    LOAD a2, 10*REGBYTES(sp)
    LOAD a3, 11*REGBYTES(sp)
    LOAD a4, 12*REGBYTES(sp)
    LOAD a5, 13*REGBYTES(sp)
    LOAD a6, 14*REGBYTES(sp)
    LOAD a7, 15*REGBYTES(sp)

    addi sp, sp, 16*REGBYTES
    mret
