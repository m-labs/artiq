#include <stdio.h>
#include <string.h>
#include <irq.h>
#include <uart.h>
#include <console.h>
#include <system.h>
#include <time.h>
#include <generated/csr.h>

#include "test_mode.h"
#include "comm.h"
#include "kernelcpu.h"
#include "elf_loader.h"
#include "exceptions.h"
#include "services.h"
#include "rtio.h"
#include "dds.h"

#ifdef ARTIQ_AMP
#include "mailbox.h"
#include "messages.h"
#endif

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
        comm_log("Too many provided symbols in object");
        symtab_init();
        return 0;
    }
    symtab[_symtab_count].name = _symtab_strptr;
    symtab[_symtab_count].target = target;
    _symtab_count++;

    while(1) {
        if(_symtab_strptr >= &_symtab_strings[sizeof(_symtab_strings)]) {
            comm_log("Provided symbol string table overflow");
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
        buffer, length, (void *)KERNELCPU_PAYLOAD_ADDRESS, 4*1024*1024);
}


#ifdef ARTIQ_AMP
static int process_msg(struct msg_unknown *umsg, int *eid, long long int *eparams)
{
    int i;

    switch(umsg->type) {
        case MESSAGE_TYPE_FINISHED:
            return KERNEL_RUN_FINISHED;
        case MESSAGE_TYPE_EXCEPTION: {
            struct msg_exception *msg = (struct msg_exception *)umsg;

            *eid = msg->eid;
            for(i=0;i<3;i++)
                eparams[i] = msg->eparams[i];
            return KERNEL_RUN_EXCEPTION;
        }
        default:
            *eid = EID_INTERNAL_ERROR;
            for(i=0;i<3;i++)
                eparams[i] = 0;
            return KERNEL_RUN_EXCEPTION;
    }
}
#endif

typedef void (*kernel_function)(void);

static int run_kernel(const char *kernel_name, int *eid, long long int *eparams)
{
    kernel_function k;
#ifdef ARTIQ_AMP
    int r;
#else
    void *jb;
#endif


    k = find_symbol(symtab, kernel_name);
    if(k == NULL) {
        comm_log("Failed to find kernel entry point '%s' in object", kernel_name);
        return KERNEL_RUN_STARTUP_FAILED;
    }

#ifdef ARTIQ_AMP
    kernelcpu_start(k);
    while(1) {
        struct msg_unknown *umsg;

        umsg = mailbox_receive();
        r = KERNEL_RUN_INVALID_STATUS;
        if(umsg)
            r = process_msg(umsg, eid, eparams);
        if(r != KERNEL_RUN_INVALID_STATUS)
            break;
    }
    kernelcpu_stop();
    return r;
#else
    jb = exception_push();
    if(exception_setjmp(jb)) {
        *eid = exception_getid(eparams);
        return KERNEL_RUN_EXCEPTION;
    } else {
        dds_init();
        rtio_init();
        flush_cpu_icache();
        k();
        exception_pop(1);
        return KERNEL_RUN_FINISHED;
    }
#endif
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

static int check_test_mode(void)
{
    char c;

    timer0_en_write(0);
    timer0_reload_write(0);
    timer0_load_write(identifier_frequency_read() >> 2);
    timer0_en_write(1);
    timer0_update_value_write(1);
    while(timer0_value_read()) {
        if(readchar_nonblock()) {
            c = readchar();
            if((c == 't')||(c == 'T'))
                return 1;
        }
        timer0_update_value_write(1);
    }
    return 0;
}

int main(void)
{
    irq_setmask(0);
    irq_setie(1);
    uart_init();

#ifdef ARTIQ_AMP
    puts("ARTIQ runtime built "__DATE__" "__TIME__" for AMP systems\n");
#else
    puts("ARTIQ runtime built "__DATE__" "__TIME__" for UP systems\n");
#endif
    blink_led();

    if(check_test_mode()) {
        puts("Entering test mode.");
        test_main();
    } else {
        puts("Entering regular mode.");
        comm_serve(load_object, run_kernel);
    }
    return 0;
}
