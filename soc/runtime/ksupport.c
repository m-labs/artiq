#include "exceptions.h"
#include "mailbox.h"
#include "messages.h"
#include "rtio.h"
#include "dds.h"

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

int comm_rpc(int rpc_num, ...);
int comm_rpc(int rpc_num, ...)
{
    /* TODO */
    return 0;
}
