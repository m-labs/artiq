#include <generated/csr.h>

#ifdef CSR_KERNEL_CPU_BASE

#include <stdio.h>
#include <string.h>
#include <system.h>

#include "kernelcpu.h"

extern char _binary_ksupport_bin_start;
extern char _binary_ksupport_bin_end;

void kernelcpu_start(void)
{
    memcpy((void *)KERNELCPU_EXEC_ADDRESS, &_binary_ksupport_bin_start,
        &_binary_ksupport_bin_end - &_binary_ksupport_bin_start);
    flush_l2_cache();
    kernel_cpu_reset_write(0);
}

void kernelcpu_stop(void)
{
    kernel_cpu_reset_write(1);
}

#endif /* CSR_KERNEL_CPU_BASE */
