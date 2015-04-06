#ifndef __MESSAGES_H
#define __MESSAGES_H

#include <stdarg.h>

enum {
    MESSAGE_TYPE_FINISHED,
    MESSAGE_TYPE_EXCEPTION,
    MESSAGE_TYPE_RPC_REQUEST,
    MESSAGE_TYPE_RPC_REPLY,
    MESSAGE_TYPE_LOG
};

struct msg_unknown {
    int type;
};

struct msg_finished {
    int type;
};

struct msg_exception {
    int type;
    int eid;
    long long int eparams[3];
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

#endif /* __MESSAGES_H */
