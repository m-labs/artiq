#ifndef __SESSION_H
#define __SESSION_H

void session_startup_kernel(void);
void session_start(void);
void session_end(void);

int session_input(void *data, int length);
void session_poll(void **data, int *length, int *close_flag);
void session_ack_consumed(int length);
void session_ack_sent(int length);

#endif /* __SESSION_H */
