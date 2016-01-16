#include <stdlib.h>
#include <system.h>
#include <spr-defs.h>
#include <hw/common.h>
#include <generated/mem.h>

#include "mailbox.h"

#define KERNELCPU_MAILBOX MMPTR(MAILBOX_BASE)

static unsigned int last_transmission;

static void _flush_cpu_dcache(void)
{
    unsigned long dccfgr;
    unsigned long cache_set_size;
    unsigned long cache_ways;
    unsigned long cache_block_size;
    unsigned long cache_size;
    int i;

    dccfgr = mfspr(SPR_DCCFGR);
    cache_ways = 1 << (dccfgr & SPR_ICCFGR_NCW);
    cache_set_size = 1 << ((dccfgr & SPR_DCCFGR_NCS) >> 3);
    cache_block_size = (dccfgr & SPR_DCCFGR_CBS) ? 32 : 16;
    cache_size = cache_set_size * cache_ways * cache_block_size;

    for (i = 0; i < cache_size; i += cache_block_size)
        mtspr(SPR_DCBIR, i);
}

void mailbox_send(void *ptr)
{
    last_transmission = (unsigned int)ptr;
    KERNELCPU_MAILBOX = last_transmission;
}

int mailbox_acknowledged(void)
{
    unsigned int m;

    m = KERNELCPU_MAILBOX;
    return !m || (m != last_transmission);
}

void mailbox_send_and_wait(void *ptr)
{
    mailbox_send(ptr);
    while(!mailbox_acknowledged());
}

void *mailbox_receive(void)
{
    unsigned int r;

    r = KERNELCPU_MAILBOX;
    if(r == last_transmission)
        return NULL;
    else {
        if(r) {
            _flush_cpu_dcache();
        }
        return (void *)r;
    }
}

void *mailbox_wait_and_receive(void)
{
    void *r;

    while(!(r = mailbox_receive()));
    return r;
}

void mailbox_acknowledge(void)
{
    KERNELCPU_MAILBOX = 0;
}
