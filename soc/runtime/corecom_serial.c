#include <stdarg.h>
#include <crc.h>
#include <uart.h>
#include <generated/csr.h>

#include "corecom.h"

/* host to device */
enum {
    MSGTYPE_REQUEST_IDENT = 1,
    MSGTYPE_LOAD_OBJECT,
    MSGTYPE_RUN_KERNEL,
};

/* device to host */
enum {
    MSGTYPE_LOG = 1,
    MSGTYPE_MESSAGE_UNRECOGNIZED,

    MSGTYPE_IDENT,

    MSGTYPE_OBJECT_LOADED,
    MSGTYPE_INCORRECT_LENGTH,
    MSGTYPE_CRC_FAILED,
    MSGTYPE_OBJECT_UNRECOGNIZED,

    MSGTYPE_KERNEL_FINISHED,
    MSGTYPE_KERNEL_STARTUP_FAILED,

    MSGTYPE_RPC_REQUEST,
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

static void receive_and_load_object(object_loader load_object)
{
    int length;
    int i;
    unsigned char buffer[256*1024];
    unsigned int crc;

    length = receive_int();
    if(length > sizeof(buffer)) {
        send_char(MSGTYPE_INCORRECT_LENGTH);
        return;
    }
    crc = receive_int();
    for(i=0;i<length;i++)
        buffer[i] = receive_char();
    if(crc32(buffer, length) != crc) {
        send_char(MSGTYPE_CRC_FAILED);
        return;
    }
    if(load_object(buffer, length))
        send_char(MSGTYPE_OBJECT_LOADED);
    else
        send_char(MSGTYPE_OBJECT_UNRECOGNIZED);
}

static void receive_and_run_kernel(kernel_runner run_kernel)
{
    int length;
    int i;
    char kernel_name[256];
    int r;

    length = receive_int();
    if(length > (sizeof(kernel_name)-1)) {
        send_char(MSGTYPE_INCORRECT_LENGTH);
        return;
    }
    for(i=0;i<length;i++)
        kernel_name[i] = receive_char();
    kernel_name[length] = 0;

    r = run_kernel(kernel_name);
    send_char(r ? MSGTYPE_KERNEL_FINISHED : MSGTYPE_KERNEL_STARTUP_FAILED);
}

void corecom_serve(object_loader load_object, kernel_runner run_kernel)
{
    char msgtype;

    while(1) {
        receive_sync();
        msgtype = receive_char();
        if(msgtype == MSGTYPE_REQUEST_IDENT) {
            send_char(MSGTYPE_IDENT);
            send_int(0x41524f52); /* "AROR" - ARTIQ runtime on OpenRISC */
            send_int(1000000000000LL/identifier_frequency_read()); /* RTIO clock period in picoseconds */
        } else if(msgtype == MSGTYPE_LOAD_OBJECT)
            receive_and_load_object(load_object);
        else if(msgtype == MSGTYPE_RUN_KERNEL)
            receive_and_run_kernel(run_kernel);
        else
            send_char(MSGTYPE_MESSAGE_UNRECOGNIZED);
    }
}

int corecom_rpc(int rpc_num, int n_args, ...)
{
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

void corecom_log(const char *fmt, ...)
{
    va_list args;
    int len;
    char outbuf[256];
    int i;

    va_start(args, fmt);
    len = vscnprintf(outbuf, sizeof(outbuf), fmt, args);
    va_end(args);

    send_char(MSGTYPE_LOG);
    send_sint(len);
    for(i=0;i<len;i++)
        send_char(outbuf[i]);
}
