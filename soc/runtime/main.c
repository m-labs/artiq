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

enum {
	MSGTYPE_REQUEST_IDENT		= 0x01,
	MSGTYPE_LOAD_KERNEL			= 0x02,
	MSGTYPE_KERNEL_FINISHED		= 0x03,
	MSGTYPE_RPC_REQUEST			= 0x04,
};

static int receive_int(void)
{
	unsigned int r;
	int i;

	r = 0;
	for(i=0;i<4;i++) {
		r <<= 8;
		r |= (unsigned char)uart_read();
	}
	return r;
}

static char receive_char(void)
{
	return uart_read();
}

static void send_int(int x)
{
	int i;

	for(i=0;i<4;i++) {
		uart_write((x & 0xff000000) >> 24);
		x <<= 8;
	}
}

static void send_sint(short int i)
{
	uart_write((i >> 8) & 0xff);
	uart_write(i & 0xff);
}

static void send_char(char c)
{
	uart_write(c);
}

static void receive_sync(void)
{
	char c;
	int recognized;

	recognized = 0;
	while(recognized < 4) {
		c = uart_read();
		if(c == 0x5a)
			recognized++;
		else
			recognized = 0;
	}
}

static void send_sync(void)
{
	send_int(0x5a5a5a5a);
}

static int ident_and_download_kernel(void *buffer, int maxlength)
{
	int length;
	int i;
	char msgtype;
	unsigned char *_buffer = buffer;

	while(1) {
		receive_sync();
		msgtype = receive_char();
		if(msgtype == MSGTYPE_REQUEST_IDENT) {
			send_int(0x41524f52); /* "AROR" - ARTIQ runtime on OpenRISC */
			send_int(1000000000000LL/identifier_frequency_read()); /* RTIO clock period in picoseconds */
		} else if(msgtype == MSGTYPE_LOAD_KERNEL) {
			length = receive_int();
			if(length > maxlength)
				return -1;
			for(i=0;i<length;i++)
				_buffer[i] = receive_char();
			send_char(0x4f); /* kernel reception OK */
			return length;
		} else
			return -1;
	}
}

static int rpc(int rpc_num, int n_args, ...)
{
	send_sync();
	send_char(MSGTYPE_RPC_REQUEST);
	send_sint(rpc_num);
	send_char(n_args);

	va_list args;
	va_start(args, n_args);
	while(n_args--)
		send_int(va_arg(args, int));
	va_end(args);

	return receive_int();
}

static void gpio_set(int channel, int value)
{
	leds_out_write(value);
}

static void rtio_set(int timestamp, int channel, int value)
{
	rtio_chan_sel_write(channel);
	rtio_o_timestamp_write(timestamp);
	rtio_o_value_write(value);
	while(!rtio_o_writable_read());
	rtio_o_we_write(1);
}

static const struct symbol syscalls[] = {
	{"__syscall_rpc",			rpc},
	{"__syscall_gpio_set",		gpio_set},
	{"__syscall_rtio_set",		rtio_set},
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
		length = ident_and_download_kernel(kbuf, sizeof(kbuf));
		if(length > 0) {
			if(load_elf(syscalls, kbuf, length, kcode, sizeof(kcode))) {
				flush_cpu_icache();
				rtio_reset_write(0);
				k();
				rtio_reset_write(1);
				send_sync();
				send_char(MSGTYPE_KERNEL_FINISHED);
			}
		}
	}
	
	return 0;
}
