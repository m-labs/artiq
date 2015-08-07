#include <string.h>
#include <generated/csr.h>

#include <dyld.h>

#include "kloader.h"
#include "log.h"
#include "flash_storage.h"
#include "mailbox.h"
#include "messages.h"

static void start_kernel_cpu(struct msg_load_request *msg)
{
    // Stop kernel CPU before messing with its code.
    kernel_cpu_reset_write(1);

    // Load kernel support code.
    extern void _binary_ksupport_elf_start, _binary_ksupport_elf_end;
    memcpy((void *)(KERNELCPU_EXEC_ADDRESS - KSUPPORT_HEADER_SIZE),
           &_binary_ksupport_elf_start,
           &_binary_ksupport_elf_end - &_binary_ksupport_elf_start);

    // Start kernel CPU.
    mailbox_send(msg);
    kernel_cpu_reset_write(0);
}

void kloader_start_bridge()
{
    start_kernel_cpu(NULL);
}

static int load_or_start_kernel(void *library, int run_kernel)
{
    static struct dyld_info library_info;
    struct msg_load_request request = {
        .library      = library,
        .library_info = &library_info,
        .run_kernel   = run_kernel,
    };
    start_kernel_cpu(&request);

    struct msg_load_reply *reply = mailbox_wait_and_receive();
    mailbox_acknowledge();

    if(reply->type != MESSAGE_TYPE_LOAD_REPLY) {
        log("BUG: unexpected reply to load/run request");
        return 0;
    }

    if(reply->error != NULL) {
        log("cannot load kernel: %s", reply->error);
        return 0;
    }

    return 1;
}

int kloader_load_library(void *library)
{
    if(!kernel_cpu_reset_read()) {
        log("BUG: attempted to load kernel library while kernel CPU is running");
        return 0;
    }

    return load_or_start_kernel(library, 0);
}

void kloader_start_kernel()
{
    load_or_start_kernel(NULL, 1);
}

int kloader_start_idle_kernel(void)
{
#if (defined CSR_SPIFLASH_BASE && defined SPIFLASH_PAGE_SIZE)
    char buffer[32*1024];
    int length;

    length = fs_read("idle_kernel", buffer, sizeof(buffer), NULL);
    if(length <= 0)
        return 0;

    return load_or_start_kernel(buffer, 1);
#else
    return 0;
#endif
}

void kloader_stop(void)
{
    kernel_cpu_reset_write(1);
    mailbox_acknowledge();
}

int kloader_validate_kpointer(void *p)
{
    unsigned int v = (unsigned int)p;
    if((v < KERNELCPU_EXEC_ADDRESS) || (v > KERNELCPU_LAST_ADDRESS)) {
        log("Received invalid pointer from kernel CPU: 0x%08x", v);
        return 0;
    }
    return 1;
}

int kloader_is_essential_kmsg(int msgtype)
{
    switch(msgtype) {
        case MESSAGE_TYPE_NOW_INIT_REQUEST:
        case MESSAGE_TYPE_NOW_SAVE:
        case MESSAGE_TYPE_LOG:
            return 1;
        default:
            return 0;
    }
}

long long int now;

void kloader_service_essential_kmsg(void)
{
    struct msg_base *umsg;

    umsg = mailbox_receive();
    if(umsg) {
        if(!kloader_validate_kpointer(umsg))
            return;
        switch(umsg->type) {
            case MESSAGE_TYPE_NOW_INIT_REQUEST: {
                struct msg_now_init_reply reply;

                reply.type = MESSAGE_TYPE_NOW_INIT_REPLY;
                reply.now = now;
                mailbox_send_and_wait(&reply);
                break;
            }
            case MESSAGE_TYPE_NOW_SAVE: {
                struct msg_now_save *msg = (struct msg_now_save *)umsg;

                now = msg->now;
                mailbox_acknowledge();
                break;
            }
            case MESSAGE_TYPE_LOG: {
                struct msg_log *msg = (struct msg_log *)umsg;

                if(msg->no_newline) {
                    lognonl_va(msg->fmt, msg->args);
                } else {
                    log_va(msg->fmt, msg->args);
                }
                mailbox_acknowledge();
                break;
            }
            default:
                /* handled elsewhere */
                break;
        }
    }
}
