#ifndef __KERNELCPU_H
#define __KERNELCPU_H

#include <hw/common.h>

#define KERNELCPU_EXEC_ADDRESS 0x40020000
#define KERNELCPU_KMAIN_ADDRESS 0x40022000

#define KERNELCPU_MAILBOX MMPTR(0xd0000000)

void kernelcpu_start(void);
void kernelcpu_stop(void);

#endif /* __KERNELCPU_H */
