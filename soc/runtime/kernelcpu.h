#ifndef __KERNELCPU_H
#define __KERNELCPU_H

#include <hw/common.h>

#define KERNELCPU_EXEC_ADDRESS 0x40020000
#define KERNELCPU_PAYLOAD_ADDRESS 0x40024000

#define KERNELCPU_MAILBOX MMPTR(0xd0000000)

void kernelcpu_start(void *addr);
void kernelcpu_stop(void);

#endif /* __KERNELCPU_H */
