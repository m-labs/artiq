.global exception_setjmp
.type exception_setjmp,@function
exception_setjmp:
    l.sw    0(r3), r1
    l.sw    4(r3), r2
    l.sw    8(r3), r9
    l.sw    12(r3), r10
    l.sw    16(r3), r14
    l.sw    20(r3), r16
    l.sw    24(r3), r18
    l.sw    28(r3), r20
    l.sw    32(r3), r22
    l.sw    36(r3), r24
    l.sw    40(r3), r26
    l.sw    44(r3), r28
    l.sw    48(r3), r30
    l.jr    r9
    l.ori   r11,r0,0

.global exception_longjmp
.type   exception_longjmp,@function
exception_longjmp:
    l.sfeqi r4, 0
    l.bnf   1f
    l.addi  r11, r4, 0
    l.ori   r11, r0, 1
1:  l.lwz   r1, 0(r3)
    l.lwz   r2, 4(r3)
    l.lwz   r9, 8(r3)
    l.lwz   r10, 12(r3)
    l.lwz   r14, 16(r3)
    l.lwz   r16, 20(r3)
    l.lwz   r18, 24(r3)
    l.lwz   r20, 28(r3)
    l.lwz   r22, 32(r3)
    l.lwz   r24, 36(r3)
    l.lwz   r26, 40(r3)
    l.lwz   r28, 44(r3)
    l.lwz   r30, 48(r3)
    l.jr    r9
    l.nop
