#include <string.h>
#include <generated/csr.h>

#include "log.h"
#include "flash_storage.h"
#include "mailbox.h"
#include "messages.h"
#include "elf_loader.h"
#include "services.h"
#include "kloader.h"

static struct symbol symtab[128];
static int _symtab_count;
static char _symtab_strings[128*16];
static char *_symtab_strptr;

static void symtab_init(void)
{
    memset(symtab, 0, sizeof(symtab));
    _symtab_count = 0;
    _symtab_strptr = _symtab_strings;
}

static int symtab_add(const char *name, void *target)
{
    if(_symtab_count >= sizeof(symtab)/sizeof(symtab[0])) {
        log("Too many provided symbols in object");
        symtab_init();
        return 0;
    }
    symtab[_symtab_count].name = _symtab_strptr;
    symtab[_symtab_count].target = target;
    _symtab_count++;

    while(1) {
        if(_symtab_strptr >= &_symtab_strings[sizeof(_symtab_strings)]) {
            log("Provided symbol string table overflow");
            symtab_init();
            return 0;
        }
        *_symtab_strptr = *name;
        _symtab_strptr++;
        if(*name == 0)
            break;
        name++;
    }

    return 1;
}

int kloader_load(void *buffer, int length)
{
    if(!kernel_cpu_reset_read()) {
        log("BUG: attempted to load while kernel CPU running");
        return 0;
    }
    symtab_init();
    return load_elf(
        resolve_service_symbol, symtab_add,
        buffer, length, (void *)KERNELCPU_PAYLOAD_ADDRESS, 4*1024*1024);
}

kernel_function kloader_find(const char *name)
{
    return find_symbol(symtab, name);
}

extern char _binary_ksupport_bin_start;
extern char _binary_ksupport_bin_end;

static void start_kernel_cpu(void *addr)
{
    memcpy((void *)KERNELCPU_EXEC_ADDRESS, &_binary_ksupport_bin_start,
        &_binary_ksupport_bin_end - &_binary_ksupport_bin_start);
    mailbox_acknowledge();
    mailbox_send(addr);
    kernel_cpu_reset_write(0);
}

void kloader_start_bridge(void)
{
    start_kernel_cpu(NULL);
}

void kloader_start_user_kernel(kernel_function k)
{
    if(!kernel_cpu_reset_read()) {
        log("BUG: attempted to start kernel CPU while already running (user kernel)");
        return;
    }
    start_kernel_cpu((void *)k);
}

void kloader_start_idle_kernel(void)
{
    char buffer[32*1024];
    int len;
    kernel_function k;

    if(!kernel_cpu_reset_read()) {
        log("BUG: attempted to start kernel CPU while already running (idle kernel)");
        return;
    }
#if (defined CSR_SPIFLASH_BASE && defined SPIFLASH_PAGE_SIZE)
    len = fs_read("idle_kernel", buffer, sizeof(buffer), NULL);
    if(len <= 0)
        return;
    if(!kloader_load(buffer, len)) {
        log("Failed to load ELF binary for idle kernel");
        return;
    }
    k = kloader_find("run");
    if(!k) {
        log("Failed to find entry point for ELF kernel");
        return;
    }
    start_kernel_cpu((void *)k);
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
    if((v < 0x40400000) || (v > (0x4fffffff - 1024*1024))) {
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

                log_va(msg->fmt, msg->args);
                mailbox_acknowledge();
                break;
            }
            default:
                /* handled elsewhere */
                break;
        }
    }
}
