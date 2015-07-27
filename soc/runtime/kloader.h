#ifndef __KLOADER_H
#define __KLOADER_H

#define KERNELCPU_EXEC_ADDRESS 0x40400000
#define KERNELCPU_PAYLOAD_ADDRESS 0x40408000

extern long long int now;

typedef void (*kernel_function)(void);

int kloader_load(void *buffer, int length);
kernel_function kloader_find(const char *name);

void kloader_start_bridge(void);
void kloader_start_idle_kernel(void);
void kloader_start_user_kernel(kernel_function k);
void kloader_stop(void);

int kloader_validate_kpointer(void *p);
int kloader_is_essential_kmsg(int msgtype);
void kloader_service_essential_kmsg(void);

#endif /* __KLOADER_H */
