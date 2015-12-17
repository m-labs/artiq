#ifndef __ANALYZER_H
#define __ANALYZER_H

void analyzer_init(void);

void analyzer_start(void);
void analyzer_end(void);

int analyzer_input(void *data, int length);
void analyzer_poll(void **data, int *length);
void analyzer_ack_consumed(int length);
void analyzer_ack_sent(int length);

#endif /* __ANALYZER_H */
