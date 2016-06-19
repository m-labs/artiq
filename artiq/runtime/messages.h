#ifndef __MESSAGES_H
#define __MESSAGES_H

#include <stdarg.h>
#include <stddef.h>
#include <stdint.h>

enum {
    MESSAGE_TYPE_LOAD_REPLY,
    MESSAGE_TYPE_NOW_INIT_REQUEST,
    MESSAGE_TYPE_NOW_INIT_REPLY,
    MESSAGE_TYPE_NOW_SAVE,
    MESSAGE_TYPE_FINISHED,
    MESSAGE_TYPE_EXCEPTION,
    MESSAGE_TYPE_WATCHDOG_SET_REQUEST,
    MESSAGE_TYPE_WATCHDOG_SET_REPLY,
    MESSAGE_TYPE_WATCHDOG_CLEAR,
    MESSAGE_TYPE_RPC_SEND,
    MESSAGE_TYPE_RPC_RECV_REQUEST,
    MESSAGE_TYPE_RPC_RECV_REPLY,
    MESSAGE_TYPE_RPC_BATCH,
    MESSAGE_TYPE_CACHE_GET_REQUEST,
    MESSAGE_TYPE_CACHE_GET_REPLY,
    MESSAGE_TYPE_CACHE_PUT_REQUEST,
    MESSAGE_TYPE_CACHE_PUT_REPLY,
    MESSAGE_TYPE_LOG,

    MESSAGE_TYPE_BRG_READY,
    MESSAGE_TYPE_BRG_TTL_O,
    MESSAGE_TYPE_BRG_TTL_OE,
    MESSAGE_TYPE_BRG_DDS_SEL,
    MESSAGE_TYPE_BRG_DDS_RESET,
    MESSAGE_TYPE_BRG_DDS_READ_REQUEST,
    MESSAGE_TYPE_BRG_DDS_READ_REPLY,
    MESSAGE_TYPE_BRG_DDS_WRITE,
    MESSAGE_TYPE_BRG_DDS_FUD,
};

struct msg_base {
    int type;
};

/* kernel messages */

struct msg_load_request {
    const void *library;
    struct dyld_info *library_info;
    int run_kernel;
};

struct msg_load_reply {
    int type;
    const char *error;
};

struct msg_now_init_reply {
    int type;
    long long int now;
};

struct msg_now_save {
    int type;
    long long int now;
};

struct msg_exception {
    int type;
    struct artiq_exception *exception;
    struct artiq_backtrace_item *backtrace;
    size_t backtrace_size;
};

struct msg_watchdog_set_request {
    int type;
    int ms;
};

struct msg_watchdog_set_reply {
    int type;
    int id;
};

struct msg_watchdog_clear {
    int type;
    int id;
};

struct msg_rpc_send {
    int type;
    long long int now;
    int service;
    const char *tag;
    va_list args;
};

struct msg_rpc_recv_request {
    int type;
    void *slot;
};

struct msg_rpc_recv_reply {
    int type;
    int alloc_size;
    struct artiq_exception *exception;
};

struct msg_cache_get_request {
    int type;
    const char *key;
};

struct msg_cache_get_reply {
    int type;
    size_t length;
    int32_t *elements;
};

struct msg_cache_put_request {
    int type;
    const char *key;
    size_t length;
    int32_t *elements;
};

struct msg_cache_put_reply {
    int type;
    int succeeded;
};

struct msg_log {
    int type;
    const char *fmt;
    va_list args;
};

/* bridge messages */

struct msg_brg_ttl_out {
    /* used for OE and O */
    int type;
    int channel;
    int value;
};

struct msg_brg_dds_sel {
    int type;
    int bus_channel;
    int channel;
};

struct msg_brg_dds_reset {
    int type;
    int bus_channel;
};

struct msg_brg_dds_read_request {
    int type;
    int bus_channel;
    unsigned int address;
};

struct msg_brg_dds_read_reply {
    int type;
    int bus_channel;
    unsigned int data;
};

struct msg_brg_dds_write {
    int type;
    int bus_channel;
    unsigned int address;
    unsigned int data;
};

struct msg_brg_dds_fud {
    int type;
    int bus_channel;
};

#endif /* __MESSAGES_H */
