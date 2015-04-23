#ifndef __SESSION_H
#define __SESSION_H

void session_start(void);
void session_end(void);

int session_input(void *data, int len);
void session_poll(void **data, int *len);
void session_ack_data(int len);
void session_ack_mem(int len);

int rpc(int rpc_num, ...);

#endif /* __SESSION_H */
