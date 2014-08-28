#include <stdarg.h>
#include <crc.h>
#include <uart.h>
#include <generated/csr.h>

#include "corecom.h"

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

int ident_and_download_kernel(void *buffer, int maxlength)
{
	int length;
	unsigned int crc;
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
			if(length > maxlength) {
				send_char(0x4c); /* Incorrect length */
				return -1;
			}
			crc = receive_int();
			for(i=0;i<length;i++)
				_buffer[i] = receive_char();
			if(crc32(buffer, length) != crc) {
				send_char(0x43); /* CRC failed */
				return -1;
			}
			send_char(0x4f); /* kernel reception OK */
			return length;
		} else
			return -1;
	}
}

int rpc(int rpc_num, int n_args, ...)
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

void kernel_finished(void)
{
	send_sync();
	send_char(MSGTYPE_KERNEL_FINISHED);
}
