#include <stdlib.h>
#include <system.h>
#include <spr-defs.h>
#include <hw/common.h>
#include <generated/mem.h>

#include "mailbox.h"

#define KERNELCPU_MAILBOX MMPTR(MAILBOX_BASE)

static unsigned int last_transmission;

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
            flush_cpu_dcache();
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
