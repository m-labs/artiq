#ifndef __KLOADER_H
#define __KLOADER_H

#include "artiq_personality.h"

#define KERNELCPU_EXEC_ADDRESS    0x40400000
#define KERNELCPU_PAYLOAD_ADDRESS 0x40420000
#define KERNELCPU_LAST_ADDRESS    (0x4fffffff - 1024*1024)
#define KSUPPORT_HEADER_SIZE      0x80

extern long long int now;

int kloader_load_library(const void *code);
void kloader_filter_backtrace(struct artiq_backtrace_item *backtrace,
                              size_t *backtrace_size);

void kloader_start_bridge(void);
int kloader_start_startup_kernel(void);
int kloader_start_idle_kernel(void);
void kloader_start_kernel(void);
void kloader_stop(void);

int kloader_validate_kpointer(void *p);
int kloader_is_essential_kmsg(int msgtype);
void kloader_service_essential_kmsg(void);

#endif /* __KLOADER_H */
