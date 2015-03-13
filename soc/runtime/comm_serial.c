#include <stdarg.h>
#include <crc.h>
#include <uart.h>
#include <generated/csr.h>

#include "comm.h"
#include "exceptions.h"

/* host to device */
enum {
    MSGTYPE_REQUEST_IDENT = 1,
    MSGTYPE_LOAD_OBJECT,
    MSGTYPE_RUN_KERNEL,
    MSGTYPE_SET_BAUD_RATE,
    MSGTYPE_SWITCH_CLOCK,
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
    MSGTYPE_KERNEL_EXCEPTION,
    MSGTYPE_KERNEL_STARTUP_FAILED,

    MSGTYPE_RPC_REQUEST,

    MSGTYPE_CLOCK_SWITCH_COMPLETED,
    MSGTYPE_CLOCK_SWITCH_FAILED,
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

static void send_llint(long long int x)
{
    int i;

    for(i=0;i<8;i++) {
        uart_write((x & 0xff00000000000000LL) >> 56);
        x <<= 8;
    }
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
    int r, eid;

    length = receive_int();
    if(length > (sizeof(kernel_name)-1)) {
        send_char(MSGTYPE_INCORRECT_LENGTH);
        return;
    }
    for(i=0;i<length;i++)
        kernel_name[i] = receive_char();
    kernel_name[length] = 0;

    r = run_kernel(kernel_name, &eid);
    switch(r) {
        case KERNEL_RUN_FINISHED:
            send_char(MSGTYPE_KERNEL_FINISHED);
            break;
        case KERNEL_RUN_EXCEPTION:
            send_char(MSGTYPE_KERNEL_EXCEPTION);
            send_int(eid);
            for(i=0;i<3;i++)
                send_llint(exception_params[i]);
            break;
        case KERNEL_RUN_STARTUP_FAILED:
            send_char(MSGTYPE_KERNEL_STARTUP_FAILED);
            break;
        default:
            comm_log("BUG: run_kernel returned unexpected value '%d'", r);
            break;
    }
}

void comm_serve(object_loader load_object, kernel_runner run_kernel)
{
    char msgtype;

    while(1) {
        receive_sync();
        msgtype = receive_char();
        if(msgtype == MSGTYPE_REQUEST_IDENT) {
            send_char(MSGTYPE_IDENT);
            send_int(0x41524f52); /* "AROR" - ARTIQ runtime on OpenRISC */
            send_int(rtio_frequency_i_read());
            send_char(rtio_frequency_fn_read());
            send_char(rtio_frequency_fd_read());
        } else if(msgtype == MSGTYPE_LOAD_OBJECT)
            receive_and_load_object(load_object);
        else if(msgtype == MSGTYPE_RUN_KERNEL)
            receive_and_run_kernel(run_kernel);
        else if(msgtype == MSGTYPE_SET_BAUD_RATE) {
            unsigned int ftw;

            ftw = ((long long)receive_int() << 32LL)/(long long)identifier_frequency_read();
            send_int(0x5a5a5a5a);
            uart_sync();
            uart_phy_tuning_word_write(ftw);
        } else if(msgtype == MSGTYPE_SWITCH_CLOCK) {
            rtiocrg_clock_sel_write(receive_char());
            send_char(MSGTYPE_CLOCK_SWITCH_COMPLETED);
        } else
            send_char(MSGTYPE_MESSAGE_UNRECOGNIZED);
    }
}

static int send_value(int type_tag, void *value)
{
    char base_type;
    int i, p;
    int len;

    base_type = type_tag;
    send_char(base_type);
    switch(base_type) {
        case 'n':
            return 0;
        case 'b':
            if(*(char *)value)
                send_char(1);
            else
                send_char(0);
            return 1;
        case 'i':
            send_int(*(int *)value);
            return 4;
        case 'I':
        case 'f':
            send_int(*(int *)value);
            send_int(*((int *)value + 1));
            return 8;
        case 'F':
            for(i=0;i<4;i++)
                send_int(*((int *)value + i));
            return 16;
        case 'l':
            len = *(int *)value;
            p = 4;
            for(i=0;i<len;i++)
                p += send_value(type_tag >> 8, (char *)value + p);
            send_char(0);
            return p;
    }
    return 0;
}

int comm_rpc(int rpc_num, ...)
{
    int type_tag;
    int eid;
    int retval;

    send_char(MSGTYPE_RPC_REQUEST);
    send_sint(rpc_num);

    va_list args;
    va_start(args, rpc_num);
    while((type_tag = va_arg(args, int)))
        send_value(type_tag, type_tag == 'n' ? NULL : va_arg(args, void *));
    va_end(args);
    send_char(0);

    eid = receive_int();
    retval = receive_int();

    if(eid != EID_NONE)
        exception_raise(eid);

    return retval;
}

void comm_log(const char *fmt, ...)
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
