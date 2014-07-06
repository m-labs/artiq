#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>

#include <irq.h>
#include <uart.h>
#include <console.h>
#include <system.h>
#include <generated/csr.h>

#include "elf_loader.h"

static void receive_sync(void)
{
	char c;
	int recognized;

	recognized = 0;
	while(1) {
		c = readchar();
		if(c == 0x5a) {
			recognized++;
			if(recognized == 4)
				return;
		} else
			recognized = 0;
	}
}

static int receive_length(void)
{
	unsigned int r;
	int i;

	r = 0;
	for(i=0;i<4;i++) {
		r <<= 8;
		r |= (unsigned char)readchar();
	}
	return r;
}

static int download_kernel(void *buffer, int maxlength)
{
	int length;
	int i;
	unsigned char *_buffer = buffer;

	receive_sync();
	length = receive_length();
	if(length > maxlength)
		return -1;
	for(i=0;i<length;i++)
		_buffer[i] = readchar();
	return length;
}

static int rpc(int rpc_num, int n_args, ...)
{
	printf("rpc_num=%d n_args=%d\n", rpc_num, n_args);

	va_list args;
	va_start(args, n_args);
	while(n_args--)
		printf("%d\n", va_arg(args, int));
	va_end(args);

	return 1;
}

static void gpio_set(int channel, int level)
{
	leds_out_write(!!level);
}

static const struct symbol syscalls[] = {
	{"__syscall_rpc",			rpc},
	{"__syscall_gpio_set",		gpio_set},
	{NULL, NULL}
};

typedef void (*kernel_function)(void);

int main(void)
{
	unsigned char kbuf[256*1024];
	unsigned char kcode[256*1024];
	kernel_function k = (kernel_function)kcode;
	int length;

	irq_setmask(0);
	irq_setie(1);
	uart_init();
	
	puts("ARTIQ runtime built "__DATE__" "__TIME__"\n");
	
	while(1) {
		length = download_kernel(kbuf, sizeof(kbuf));
		if(length > 0) {
			load_elf(syscalls, kbuf, length, kcode, sizeof(kcode));
			flush_cpu_icache();
			k();
		}
	}
	
	return 0;
}
