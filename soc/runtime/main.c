#include <stdio.h>
#include <irq.h>
#include <uart.h>
#include <system.h>

#include "corecom.h"
#include "elf_loader.h"
#include "symbols.h"
#include "rtio.h"
#include "dds.h"

typedef void (*kernel_function)(void);

int main(void)
{
    unsigned char kbuf[256*1024];
    unsigned char kcode[256*1024];
    kernel_function k;
    int length;

    irq_setmask(0);
    irq_setie(1);
    uart_init();
    
    puts("ARTIQ runtime built "__DATE__" "__TIME__"\n");

    while(1) {
        length = ident_and_download_kernel(kbuf, sizeof(kbuf));
        if(length > 0) {
            k = load_elf(resolve_symbol, "run", kbuf, length, kcode, sizeof(kcode));
            if(k != NULL) {
                dds_init();
                rtio_init();
                flush_cpu_icache();
                k();
                kernel_finished();
            }
        }
    }

    return 0;
}
