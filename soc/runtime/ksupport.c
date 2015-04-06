#include <stdarg.h>

#include "exceptions.h"
#include "mailbox.h"
#include "messages.h"
#include "rtio.h"
#include "dds.h"

/* for the prototypes for comm_rpc and comm_log */
#include "comm.h"

void exception_handler(unsigned long vect, unsigned long *sp);
void exception_handler(unsigned long vect, unsigned long *sp)
{
    struct msg_exception msg;
    int i;

    msg.type = MESSAGE_TYPE_EXCEPTION;
    msg.eid = EID_INTERNAL_ERROR;
    for(i=0;i<3;i++)
        msg.eparams[i] = 0;
    mailbox_send_and_wait(&msg);
    while(1);
}

typedef void (*kernel_function)(void);

int main(void);
int main(void)
{
    kernel_function k;
    void *jb;

    jb = exception_push();
    if(exception_setjmp(jb)) {
        struct msg_exception msg;

        msg.type = MESSAGE_TYPE_EXCEPTION;
        msg.eid = exception_getid(msg.eparams);
        mailbox_send_and_wait(&msg);
    } else {
        struct msg_finished msg;

        k = mailbox_receive();
        if(!k)
            exception_raise(EID_INTERNAL_ERROR);
        dds_init();
        rtio_init();
        k();
        exception_pop(1);

        msg.type = MESSAGE_TYPE_FINISHED;
        mailbox_send_and_wait(&msg);
    }
    while(1);
}

int comm_rpc(int rpc_num, ...)
{
    struct msg_rpc_request request;
    struct msg_rpc_reply *reply;
    int r;

    request.type = MESSAGE_TYPE_RPC_REQUEST;
    request.rpc_num = rpc_num;
    va_start(request.args, rpc_num);
    mailbox_send_and_wait(&request);
    va_end(request.args);

    reply = mailbox_wait_and_receive();
    if(reply->type != MESSAGE_TYPE_RPC_REPLY)
        exception_raise(EID_INTERNAL_ERROR);
    r = reply->ret_val;
    mailbox_acknowledge();
    return r;
}

void comm_log(const char *fmt, ...)
{
    struct msg_log request;

    request.type = MESSAGE_TYPE_LOG;
    request.fmt = fmt;
    va_start(request.args, fmt);
    mailbox_send_and_wait(&request);
    va_end(request.args);
}
