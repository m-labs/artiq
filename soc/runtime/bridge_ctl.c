#include <stdio.h>

#include "kloader.h"
#include "mailbox.h"
#include "messages.h"

void brg_start(void)
{
    struct msg_base *umsg;

    kloader_start_bridge();

    while(1) {
        umsg = mailbox_wait_and_receive();
        if(umsg->type == MESSAGE_TYPE_BRG_READY) {
            mailbox_acknowledge();
            break;
        } else {
            printf("Warning: unexpected message %d from AMP bridge\n", umsg->type);
            mailbox_acknowledge();
        }
    }
}

void brg_stop(void)
{
    kloader_stop();
}

void brg_ttloe(int n, int value)
{
    struct msg_brg_ttl_out msg;

    msg.type = MESSAGE_TYPE_BRG_TTL_OE;
    msg.channel = n;
    msg.value = value;
    mailbox_send_and_wait(&msg);
}

void brg_ttlo(int n, int value)
{
    struct msg_brg_ttl_out msg;

    msg.type = MESSAGE_TYPE_BRG_TTL_O;
    msg.channel = n;
    msg.value = value;
    mailbox_send_and_wait(&msg);
}

void brg_ddsinitall(void)
{
    struct msg_base msg;

    msg.type = MESSAGE_TYPE_BRG_DDS_INITALL;
    mailbox_send_and_wait(&msg);
}

void brg_ddssel(int channel)
{
    struct msg_brg_dds_sel msg;

    msg.type = MESSAGE_TYPE_BRG_DDS_SEL;
    msg.channel = channel;
    mailbox_send_and_wait(&msg);
}

void brg_ddsreset(void)
{
    struct msg_base msg;

    msg.type = MESSAGE_TYPE_BRG_DDS_RESET;
    mailbox_send_and_wait(&msg);
}

unsigned int brg_ddsread(unsigned int address)
{
    struct msg_brg_dds_read_request msg;
    struct msg_brg_dds_read_reply *rmsg;
    unsigned int r;

    msg.type = MESSAGE_TYPE_BRG_DDS_READ_REQUEST;
    msg.address = address;
    mailbox_send(&msg);
    while(1) {
        rmsg = mailbox_wait_and_receive();
        if(rmsg->type == MESSAGE_TYPE_BRG_DDS_READ_REPLY) {
            r = rmsg->data;
            mailbox_acknowledge();
            return r;
        } else {
            printf("Warning: unexpected message %d from AMP bridge\n", rmsg->type);
            mailbox_acknowledge();
        }
    }
}

void brg_ddswrite(unsigned int address, unsigned int data)
{
    struct msg_brg_dds_write msg;

    msg.type = MESSAGE_TYPE_BRG_DDS_WRITE;
    msg.address = address;
    msg.data = data;
    mailbox_send_and_wait(&msg);
}

void brg_ddsfud(void)
{
    struct msg_base msg;

    msg.type = MESSAGE_TYPE_BRG_DDS_FUD;
    mailbox_send_and_wait(&msg);
}
