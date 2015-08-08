#ifndef __SESSION_H
#define __SESSION_H

void session_start(void);
void session_end(void);

int session_input(void *data, int length);
void session_poll(void **data, int *length);
void session_ack(int length);

#endif /* __SESSION_H */
