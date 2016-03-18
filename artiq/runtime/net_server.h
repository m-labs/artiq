#ifndef __NET_SERVER_H
#define __NET_SERVER_H

struct net_server_connstate;
struct tcp_pcb;

struct net_server_instance {
    int port;

    void (*start)(void);
    void (*end)(void);
    int (*input)(void *data, int length);
    void (*poll)(void **data, int *length, int *close_flag);
    void (*ack_consumed)(int length);
    void (*ack_sent)(int length);

    /* internal use */
    struct tcp_pcb *listen_pcb;
    struct net_server_connstate *open_session_cs;
    struct tcp_pcb *open_session_pcb;
};

void net_server_init(struct net_server_instance *instance);
void net_server_service(void);

#endif /* __NET_SERVER_H */
