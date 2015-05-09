#ifndef __MESSAGES_H
#define __MESSAGES_H

#include <stdarg.h>

enum {
    MESSAGE_TYPE_NOW_INIT_REQUEST,
    MESSAGE_TYPE_NOW_INIT_REPLY,
    MESSAGE_TYPE_NOW_SAVE,
    MESSAGE_TYPE_FINISHED,
    MESSAGE_TYPE_EXCEPTION,
    MESSAGE_TYPE_WATCHDOG_SET_REQUEST,
    MESSAGE_TYPE_WATCHDOG_SET_REPLY,
    MESSAGE_TYPE_WATCHDOG_CLEAR,
    MESSAGE_TYPE_RPC_REQUEST,
    MESSAGE_TYPE_RPC_REPLY,
    MESSAGE_TYPE_LOG,

    MESSAGE_TYPE_BRG_READY,
    MESSAGE_TYPE_BRG_TTL_O,
    MESSAGE_TYPE_BRG_TTL_OE,
    MESSAGE_TYPE_BRG_DDS_INITALL,
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
    int eid;
    long long int eparams[3];
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

struct msg_rpc_request {
    int type;
    int rpc_num;
    va_list args;
};

struct msg_rpc_reply {
    int type;
    int eid;
    int retval;
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
    int channel;
};

struct msg_brg_dds_read_request {
    int type;
    unsigned int address;
};

struct msg_brg_dds_read_reply {
    int type;
    unsigned int data;
};

struct msg_brg_dds_write {
    int type;
    unsigned int address;
    unsigned int data;
};

#endif /* __MESSAGES_H */
