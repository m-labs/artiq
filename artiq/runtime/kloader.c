#include <string.h>
#include <generated/csr.h>

#include <dyld.h>

#include "kloader.h"
#include "log.h"
#include "clock.h"
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

static int load_or_start_kernel(const void *library, int run_kernel)
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
        core_log("BUG: unexpected reply to load/run request\n");
        return 0;
    }

    if(reply->error != NULL) {
        core_log("cannot load kernel: %s\n", reply->error);
        return 0;
    }

    return 1;
}

int kloader_load_library(const void *library)
{
    if(!kernel_cpu_reset_read()) {
        core_log("BUG: attempted to load kernel library while kernel CPU is running\n");
        return 0;
    }

    return load_or_start_kernel(library, 0);
}

void kloader_filter_backtrace(struct artiq_backtrace_item *backtrace,
                              size_t *backtrace_size) {
    struct artiq_backtrace_item *cursor = backtrace;

    // Remove all backtrace items belonging to ksupport and subtract
    // shared object base from the addresses.
    for(int i = 0; i < *backtrace_size; i++) {
        if(backtrace[i].function > KERNELCPU_PAYLOAD_ADDRESS) {
            backtrace[i].function -= KERNELCPU_PAYLOAD_ADDRESS;
            *cursor++ = backtrace[i];
        }
    }

    *backtrace_size = cursor - backtrace;
}

void kloader_start_kernel()
{
    load_or_start_kernel(NULL, 1);
}

static int kloader_start_flash_kernel(char *key)
{
#if (defined CSR_SPIFLASH_BASE && defined CONFIG_SPIFLASH_PAGE_SIZE)
    char buffer[32*1024];
    unsigned int length, remain;

    length = fs_read(key, buffer, sizeof(buffer), &remain);
    if(length <= 0)
        return 0;

    if(remain) {
        core_log("ERROR: kernel %s is too large\n", key);
        return 0;
    }

    return load_or_start_kernel(buffer, 1);
#else
    return 0;
#endif
}

int kloader_start_startup_kernel(void)
{
    return kloader_start_flash_kernel("startup_kernel");
}

int kloader_start_idle_kernel(void)
{
    return kloader_start_flash_kernel("idle_kernel");
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
        core_log("Received invalid pointer from kernel CPU: 0x%08x\n", v);
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
        case MESSAGE_TYPE_WATCHDOG_SET_REQUEST:
        case MESSAGE_TYPE_WATCHDOG_CLEAR:
            return 1;
        default:
            return 0;
    }
}

static long long int now = 0;

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

                core_log_va(msg->fmt, msg->args);
                mailbox_acknowledge();
                break;
            }
            case MESSAGE_TYPE_WATCHDOG_SET_REQUEST: {
                struct msg_watchdog_set_request *msg = (struct msg_watchdog_set_request *)umsg;
                struct msg_watchdog_set_reply reply;

                reply.type = MESSAGE_TYPE_WATCHDOG_SET_REPLY;
                reply.id = watchdog_set(msg->ms);
                mailbox_send_and_wait(&reply);
                break;
            }
            case MESSAGE_TYPE_WATCHDOG_CLEAR: {
                struct msg_watchdog_clear *msg = (struct msg_watchdog_clear *)umsg;

                watchdog_clear(msg->id);
                mailbox_acknowledge();
                break;
            }
            default:
                /* handled elsewhere */
                break;
        }
    }
}
