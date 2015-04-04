#include "kernelcpu.h"
#include "exceptions.h"
#include "comm.h"
#include "rtio.h"
#include "dds.h"

void exception_handler(unsigned long vect, unsigned long *sp);
void exception_handler(unsigned long vect, unsigned long *sp)
{
    /* TODO: report hardware exception to comm CPU */
    for(;;);
}

typedef void (*kernel_function)(void);

int main(void);
int main(void)
{
    kernel_function k;
    void *jb;

    k = (kernel_function)KERNELCPU_MAILBOX;

    jb = exception_push();
    if(exception_setjmp(jb))
        KERNELCPU_MAILBOX = KERNEL_RUN_EXCEPTION;
    else {
        dds_init();
        rtio_init();
        k();
        exception_pop(1);
        KERNELCPU_MAILBOX = KERNEL_RUN_FINISHED;
    }
    while(1);
}

int comm_rpc(int rpc_num, ...);
int comm_rpc(int rpc_num, ...)
{
    /* TODO */
    return 0;
}
