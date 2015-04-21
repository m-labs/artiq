#ifndef __SESSION_H
#define __SESSION_H

void session_start(void);
void session_end(void);

int session_input(void *data, int len);
void session_poll(void **data, int *len);
void session_ack(int len);

int rpc(int rpc_num, ...);
void comm_service(void);

#endif /* __SESSION_H */
