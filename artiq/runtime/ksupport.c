#include <stdarg.h>
#include <string.h>
#include <stdio.h>
#include <math.h>
#include <generated/csr.h>

#include <link.h>
#include <dlfcn.h>
#include <dyld.h>
#include <unwind.h>

#include "ksupport.h"
#include "mailbox.h"
#include "messages.h"
#include "artiq_personality.h"
#include "rtio.h"
#include "dds.h"
#include "i2c.h"

#define KERNELCPU_EXEC_ADDRESS    0x40400000
#define KERNELCPU_PAYLOAD_ADDRESS 0x40420000
#define KERNELCPU_LAST_ADDRESS    0x4fffffff
#define KSUPPORT_HEADER_SIZE      0x80

long lround(double x);

void ksupport_abort(void);
static void attribute_writeback(void *);

int64_t now;

/* compiler-rt symbols */
extern void __divsi3, __modsi3, __ledf2, __gedf2, __unorddf2, __eqdf2, __ltdf2,
    __nedf2, __gtdf2, __negsf2, __negdf2, __addsf3, __subsf3, __mulsf3,
    __divsf3, __lshrdi3, __muldi3, __divdi3, __ashldi3, __ashrdi3,
    __udivmoddi4, __floatsisf, __floatunsisf, __fixsfsi, __fixunssfsi,
    __adddf3, __subdf3, __muldf3, __divdf3, __floatsidf, __floatunsidf,
    __floatdidf, __fixdfsi, __fixdfdi, __fixunsdfsi, __clzsi2, __ctzsi2,
    __udivdi3, __umoddi3, __moddi3, __powidf2;

/* artiq_personality symbols */
extern void __artiq_personality;

struct symbol {
    const char *name;
    void *addr;
};

static const struct symbol runtime_exports[] = {
    /* compiler-rt */
    {"__divsi3", &__divsi3},
    {"__modsi3", &__modsi3},
    {"__ledf2", &__ledf2},
    {"__gedf2", &__gedf2},
    {"__unorddf2", &__unorddf2},
    {"__eqdf2", &__eqdf2},
    {"__ltdf2", &__ltdf2},
    {"__nedf2", &__nedf2},
    {"__gtdf2", &__gtdf2},
    {"__negsf2", &__negsf2},
    {"__negdf2", &__negdf2},
    {"__addsf3", &__addsf3},
    {"__subsf3", &__subsf3},
    {"__mulsf3", &__mulsf3},
    {"__divsf3", &__divsf3},
    {"__lshrdi3", &__lshrdi3},
    {"__muldi3", &__muldi3},
    {"__divdi3", &__divdi3},
    {"__ashldi3", &__ashldi3},
    {"__ashrdi3", &__ashrdi3},
    {"__udivmoddi4", &__udivmoddi4},
    {"__floatsisf", &__floatsisf},
    {"__floatunsisf", &__floatunsisf},
    {"__fixsfsi", &__fixsfsi},
    {"__fixunssfsi", &__fixunssfsi},
    {"__adddf3", &__adddf3},
    {"__subdf3", &__subdf3},
    {"__muldf3", &__muldf3},
    {"__divdf3", &__divdf3},
    {"__floatsidf", &__floatsidf},
    {"__floatunsidf", &__floatunsidf},
    {"__floatdidf", &__floatdidf},
    {"__fixdfsi", &__fixdfsi},
    {"__fixdfdi", &__fixdfdi},
    {"__fixunsdfsi", &__fixunsdfsi},
    {"__clzsi2", &__clzsi2},
    {"__ctzsi2", &__ctzsi2},
    {"__udivdi3", &__udivdi3},
    {"__umoddi3", &__umoddi3},
    {"__moddi3", &__moddi3},
    {"__powidf2", &__powidf2},

    /* libm */
    {"sqrt", &sqrt},
    {"lround", &lround},

    /* exceptions */
    {"_Unwind_Resume", &_Unwind_Resume},
    {"__artiq_personality", &__artiq_personality},
    {"__artiq_raise", &__artiq_raise},
    {"__artiq_reraise", &__artiq_reraise},
    {"strcmp", &strcmp},
    {"strlen", &strlen},
    {"abort", &ksupport_abort},

    /* proxified syscalls */
    {"core_log", &core_log},

    {"now", &now},

    {"watchdog_set", &watchdog_set},
    {"watchdog_clear", &watchdog_clear},

    {"printf", &core_log},
    {"send_rpc", &send_rpc},
    {"recv_rpc", &recv_rpc},

    /* direct syscalls */
    {"rtio_init", &rtio_init},
    {"rtio_get_counter", &rtio_get_counter},
    {"rtio_log", &rtio_log},
    {"rtio_output", &rtio_output},
    {"rtio_input_timestamp", &rtio_input_timestamp},
    {"rtio_input_data", &rtio_input_data},

#if ((defined CONFIG_RTIO_DDS_COUNT) && (CONFIG_RTIO_DDS_COUNT > 0))
    {"dds_init", &dds_init},
    {"dds_init_sync", &dds_init_sync},
    {"dds_batch_enter", &dds_batch_enter},
    {"dds_batch_exit", &dds_batch_exit},
    {"dds_set", &dds_set},
#endif

    {"i2c_init", &i2c_init},
    {"i2c_start", &i2c_start},
    {"i2c_stop", &i2c_stop},
    {"i2c_write", &i2c_write},
    {"i2c_read", &i2c_read},

    {"cache_get", &cache_get},
    {"cache_put", &cache_put},

    /* end */
    {NULL, NULL}
};

long lround(double x)
{
    return x < 0 ? floor(x) : ceil(x);
}

/* called by libunwind */
int fprintf(FILE *stream, const char *fmt, ...)
{
    va_list args;
    va_start(args, fmt);

    char buf[256];
    int len = vscnprintf(buf, sizeof(buf), fmt, args);

    va_end(args);

    struct msg_log request;
    request.type = MESSAGE_TYPE_LOG;
    request.buf = buf;
    request.len = len;
    mailbox_send_and_wait(&request);

    return 0;
}

/* called by libunwind */
int dladdr (const void *address, Dl_info *info)
{
    /* we don't try to resolve names */
    return 0;
}

/* called by libunwind */
int dl_iterate_phdr (int (*callback)(struct dl_phdr_info *, size_t, void *), void *data)
{
    Elf32_Ehdr *ehdr;
    struct dl_phdr_info phdr_info;
    int retval;

    ehdr = (Elf32_Ehdr *)(KERNELCPU_EXEC_ADDRESS - KSUPPORT_HEADER_SIZE);
    phdr_info = (struct dl_phdr_info){
        .dlpi_addr  = 0, /* absolutely linked */
        .dlpi_name  = "<ksupport>",
        .dlpi_phdr  = (Elf32_Phdr*) ((intptr_t)ehdr + ehdr->e_phoff),
        .dlpi_phnum = ehdr->e_phnum,
    };
    retval = callback(&phdr_info, sizeof(phdr_info), data);
    if(retval)
        return retval;

    ehdr = (Elf32_Ehdr *)KERNELCPU_PAYLOAD_ADDRESS;
    phdr_info = (struct dl_phdr_info){
        .dlpi_addr  = KERNELCPU_PAYLOAD_ADDRESS,
        .dlpi_name  = "<kernel>",
        .dlpi_phdr  = (Elf32_Phdr*) ((intptr_t)ehdr + ehdr->e_phoff),
        .dlpi_phnum = ehdr->e_phnum,
    };
    retval = callback(&phdr_info, sizeof(phdr_info), data);
    return retval;
}

static Elf32_Addr resolve_runtime_export(const char *name)
{
    const struct symbol *sym = runtime_exports;
    while(sym->name) {
        if(!strcmp(sym->name, name))
            return (Elf32_Addr)sym->addr;
        ++sym;
    }
    return 0;
}

void exception_handler(unsigned long vect, unsigned long *regs,
                       unsigned long pc, unsigned long ea);
void exception_handler(unsigned long vect, unsigned long *regs,
                       unsigned long pc, unsigned long ea)
{
    artiq_raise_from_c("InternalError",
        "Hardware exception {0} at PC 0x{1:08x}, EA 0x{2:08x}",
        vect, pc, ea);
}

static void now_init(void)
{
    struct msg_base request;
    struct msg_now_init_reply *reply;

    request.type = MESSAGE_TYPE_NOW_INIT_REQUEST;
    mailbox_send_and_wait(&request);

    reply = mailbox_wait_and_receive();
    if(reply->type != MESSAGE_TYPE_NOW_INIT_REPLY) {
        core_log("Malformed MESSAGE_TYPE_NOW_INIT_REQUEST reply type %d\n",
                 reply->type);
        while(1);
    }
    now = reply->now;
    mailbox_acknowledge();
}

static void now_save(void)
{
    struct msg_now_save request;

    request.type = MESSAGE_TYPE_NOW_SAVE;
    request.now = now;
    mailbox_send_and_wait(&request);
}

int main(void);
int main(void)
{
    static struct dyld_info library_info;

    struct msg_load_request *request = mailbox_wait_and_receive();
    struct msg_load_reply load_reply = {
        .type = MESSAGE_TYPE_LOAD_REPLY,
        .error = NULL
    };

    if(!dyld_load(request->library, KERNELCPU_PAYLOAD_ADDRESS,
                  resolve_runtime_export, &library_info,
                  &load_reply.error)) {
        mailbox_send(&load_reply);
        while(1);
    }

    void *__bss_start = dyld_lookup("__bss_start", &library_info);
    void *_end = dyld_lookup("_end", &library_info);
    memset(__bss_start, 0, _end - __bss_start);

    void (*kernel_run)() = library_info.init;
    void *typeinfo = dyld_lookup("typeinfo", &library_info);

    mailbox_send_and_wait(&load_reply);

    now_init();
    kernel_run();
    now_save();

    attribute_writeback(typeinfo);

    struct msg_base finished_reply;
    finished_reply.type = MESSAGE_TYPE_FINISHED;
    mailbox_send_and_wait(&finished_reply);

    while(1);
}

/* called from __artiq_personality */
void __artiq_terminate(struct artiq_exception *artiq_exn,
                       uintptr_t *backtrace,
                       size_t backtrace_size)
{
    struct msg_exception msg;

    now_save();

    uintptr_t *cursor = backtrace;

    // Remove all backtrace items belonging to ksupport and subtract
    // shared object base from the addresses.
    for(int i = 0; i < backtrace_size; i++) {
        if(backtrace[i] > KERNELCPU_PAYLOAD_ADDRESS) {
            backtrace[i] -= KERNELCPU_PAYLOAD_ADDRESS;
            *cursor++ = backtrace[i];
        }
    }

    backtrace_size = cursor - backtrace;

    msg.type = MESSAGE_TYPE_EXCEPTION;
    msg.exception = artiq_exn;
    msg.backtrace = backtrace;
    msg.backtrace_size = backtrace_size;
    mailbox_send(&msg);

    while(1);
}

void ksupport_abort()
{
    artiq_raise_from_c("InternalError", "abort() called; check device log for details",
                       0, 0, 0);
}

int watchdog_set(int ms)
{
    struct msg_watchdog_set_request request;
    struct msg_watchdog_set_reply *reply;
    int id;

    request.type = MESSAGE_TYPE_WATCHDOG_SET_REQUEST;
    request.ms = ms;
    mailbox_send_and_wait(&request);

    reply = mailbox_wait_and_receive();
    if(reply->type != MESSAGE_TYPE_WATCHDOG_SET_REPLY) {
        core_log("Malformed MESSAGE_TYPE_WATCHDOG_SET_REQUEST reply type %d\n",
                 reply->type);
        while(1);
    }
    id = reply->id;
    mailbox_acknowledge();

    return id;
}

void watchdog_clear(int id)
{
    struct msg_watchdog_clear request;

    request.type = MESSAGE_TYPE_WATCHDOG_CLEAR;
    request.id = id;
    mailbox_send_and_wait(&request);
}

void send_rpc(int service, const char *tag, void **data)
{
    struct msg_rpc_send request;

    if(service != 0)
        request.type = MESSAGE_TYPE_RPC_SEND;
    else
        request.type = MESSAGE_TYPE_RPC_BATCH;
    request.service = service;
    request.tag = tag;
    request.data = data;
    mailbox_send_and_wait(&request);
}

int recv_rpc(void *slot)
{
    struct msg_rpc_recv_request request;
    struct msg_rpc_recv_reply *reply;

    request.type = MESSAGE_TYPE_RPC_RECV_REQUEST;
    request.slot = slot;
    mailbox_send_and_wait(&request);

    reply = mailbox_wait_and_receive();
    if(reply->type != MESSAGE_TYPE_RPC_RECV_REPLY) {
        core_log("Malformed MESSAGE_TYPE_RPC_RECV_REQUEST reply type %d\n",
                 reply->type);
        while(1);
    }

    if(reply->exception) {
        struct artiq_exception exception;
        memcpy(&exception, reply->exception,
               sizeof(struct artiq_exception));
        mailbox_acknowledge();
        __artiq_raise(&exception);
    } else {
        int alloc_size = reply->alloc_size;
        mailbox_acknowledge();
        return alloc_size;
    }
}

struct attr_desc {
    uint32_t offset;
    const char *tag;
    const char *name;
};

struct type_desc {
    struct attr_desc **attributes;
    void **objects;
};

void attribute_writeback(void *utypes)
{
    struct type_desc **types = (struct type_desc **)utypes;
    while(*types) {
        struct type_desc *type = *types++;

        size_t attr_count = 0;
        for(struct attr_desc **attr = type->attributes; *attr; attr++)
            attr_count++;

        void **objects = type->objects;
        while(*objects) {
            void *object = *objects++;

            struct attr_desc **attrs = type->attributes;
            while(*attrs) {
                struct attr_desc *attr = *attrs++;

                if(attr->tag) {
                    uintptr_t value = (uintptr_t)object + attr->offset;
                    void *args[] = {
                        &object,
                        &attr->name,
                        (void*)value
                    };
                    send_rpc(0, attr->tag, args);
                }
            }
        }
    }
}

struct artiq_list cache_get(const char *key)
{
    struct msg_cache_get_request request;
    struct msg_cache_get_reply *reply;

    request.type = MESSAGE_TYPE_CACHE_GET_REQUEST;
    request.key = key;
    mailbox_send_and_wait(&request);

    reply = mailbox_wait_and_receive();
    if(reply->type != MESSAGE_TYPE_CACHE_GET_REPLY) {
        core_log("Malformed MESSAGE_TYPE_CACHE_GET_REQUEST reply type %d\n",
                 reply->type);
        while(1);
    }

    return (struct artiq_list) { reply->length, reply->elements };
}

void cache_put(const char *key, struct artiq_list value)
{
    struct msg_cache_put_request request;
    struct msg_cache_put_reply *reply;

    request.type = MESSAGE_TYPE_CACHE_PUT_REQUEST;
    request.key = key;
    request.elements = value.elements;
    request.length = value.length;
    mailbox_send_and_wait(&request);

    reply = mailbox_wait_and_receive();
    if(reply->type != MESSAGE_TYPE_CACHE_PUT_REPLY) {
        core_log("Malformed MESSAGE_TYPE_CACHE_PUT_REQUEST reply type %d\n",
                 reply->type);
        while(1);
    }

    if(!reply->succeeded) {
        artiq_raise_from_c("CacheError",
            "cannot put into a busy cache row",
            0, 0, 0);
    }
}

void core_log(const char *fmt, ...)
{
    va_list args;
    va_start(args, fmt);

    char buf[256];
    int len = vscnprintf(buf, sizeof(buf), fmt, args);

    va_end(args);

    struct msg_log request;
    request.type = MESSAGE_TYPE_LOG;
    request.buf = buf;
    request.len = len;
    mailbox_send_and_wait(&request);
}
