#include <stdio.h>
#include <string.h>
#include <irq.h>
#include <uart.h>
#include <system.h>
#include <time.h>
#include <generated/csr.h>

#include "corecom.h"
#include "elf_loader.h"
#include "exceptions.h"
#include "services.h"
#include "rtio.h"
#include "dds.h"

static unsigned char kcode[256*1024];

static struct symbol symtab[128];
static int _symtab_count;
static char _symtab_strings[128*16];
static char *_symtab_strptr;


static void symtab_init(void)
{
    memset(symtab, 0, sizeof(symtab));
    _symtab_count = 0;
    _symtab_strptr = _symtab_strings;
}

static int symtab_add(const char *name, void *target)
{
    if(_symtab_count >= sizeof(symtab)/sizeof(symtab[0])) {
        corecom_log("Too many provided symbols in object");
        symtab_init();
        return 0;
    }
    symtab[_symtab_count].name = _symtab_strptr;
    symtab[_symtab_count].target = target;
    _symtab_count++;

    while(1) {
        if(_symtab_strptr >= &_symtab_strings[sizeof(_symtab_strings)]) {
            corecom_log("Provided symbol string table overflow");
            symtab_init();
            return 0;
        }
        *_symtab_strptr = *name;
        _symtab_strptr++;
        if(*name == 0)
            break;
        name++;
    }

    return 1;
}

static int load_object(void *buffer, int length)
{
    symtab_init();
    return load_elf(
        resolve_service_symbol, symtab_add,
        buffer, length, kcode, sizeof(kcode));
}

typedef void (*kernel_function)(void);

static int run_kernel(const char *kernel_name, int *eid)
{
    kernel_function k;
    struct exception_env ee;
    int exception_occured;

    k = find_symbol(symtab, kernel_name);
    if(k == NULL) {
        corecom_log("Failed to find kernel entry point '%s' in object", kernel_name);
        return KERNEL_RUN_STARTUP_FAILED;
    }

    exception_occured = exception_catch(&ee, eid);
    if(exception_occured)
        return KERNEL_RUN_EXCEPTION;
    else {
        rtio_init();
        flush_cpu_icache();
        k();
        exception_pop();
        return KERNEL_RUN_FINISHED;
    }
}

static void blink_led(void)
{
    int i, ev, p;

    p = identifier_frequency_read()/10;
    time_init();
    for(i=0;i<3;i++) {
        leds_out_write(1);
        while(!elapsed(&ev, p));
        leds_out_write(0);
        while(!elapsed(&ev, p));
    }
}

int main(void)
{
    irq_setmask(0);
    irq_setie(1);
    uart_init();
    
    puts("ARTIQ runtime built "__DATE__" "__TIME__"\n");
    dds_init();
    blink_led();
    corecom_serve(load_object, run_kernel);
    return 0;
}
