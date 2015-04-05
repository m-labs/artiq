#ifndef __MESSAGES_H
#define __MESSAGES_H

enum {
    MESSAGE_TYPE_FINISHED,
    MESSAGE_TYPE_EXCEPTION
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

#endif /* __MESSAGES_H */
