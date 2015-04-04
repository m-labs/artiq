#include <stdio.h>
#include <string.h>
#include <system.h>

#include <generated/csr.h>

#include "kernelcpu.h"

extern char _binary_ksupport_bin_start;
extern char _binary_ksupport_bin_end;

void kernelcpu_start(void *addr)
{
    memcpy((void *)KERNELCPU_EXEC_ADDRESS, &_binary_ksupport_bin_start,
        &_binary_ksupport_bin_end - &_binary_ksupport_bin_start);
    KERNELCPU_MAILBOX = (unsigned int)addr;
    flush_l2_cache();
    kernel_cpu_reset_write(0);
}

void kernelcpu_stop(void)
{
    kernel_cpu_reset_write(1);
}
