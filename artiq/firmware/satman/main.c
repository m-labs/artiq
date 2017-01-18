#include <alloc.h>
#include <irq.h>
#include <uart.h>
#include <system.h>
#include <generated/csr.h>

extern void _fheap, _eheap;

extern void rust_main();

int main(void)
{
    irq_setmask(0);
    irq_setie(1);
    uart_init();

    alloc_give(&_fheap, &_eheap - &_fheap);

    rust_main();

    return 0;
}
