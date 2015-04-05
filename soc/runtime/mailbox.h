#ifndef __MAILBOX_H
#define __MAILBOX_H

void mailbox_send(void *ptr);
int mailbox_acknowledged(void);
void mailbox_send_and_wait(void *ptr);

void *mailbox_receive(void);
void mailbox_acknowledge(void);

#endif /* __MAILBOX_H */
