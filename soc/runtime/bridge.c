#include "mailbox.h"
#include "messages.h"
#include "rtio.h"
#include "dds.h"
#include "bridge.h"

static void send_ready(void)
{
    struct msg_base msg;

    msg.type = MESSAGE_TYPE_BRG_READY;
    mailbox_send_and_wait(&msg);    
}

void bridge_main(void)
{
    struct msg_base *umsg;

    rtio_init();
    send_ready();
    while(1) {
        umsg = mailbox_wait_and_receive();
        switch(umsg->type) {
            case MESSAGE_TYPE_BRG_TTL_OE: {
                struct msg_brg_ttl_out *msg;

                msg = (struct msg_brg_ttl_out *)umsg;
                rtio_set_oe(rtio_get_counter() + 8000, msg->channel, msg->value);
                mailbox_acknowledge();
                break;
            }
            case MESSAGE_TYPE_BRG_TTL_O: {
                struct msg_brg_ttl_out *msg;

                msg = (struct msg_brg_ttl_out *)umsg;
                rtio_set_o(rtio_get_counter() + 8000, msg->channel, msg->value);
                mailbox_acknowledge();
                break;
            }
            case MESSAGE_TYPE_BRG_DDS_SEL: {
                struct msg_brg_dds_sel *msg;

                msg = (struct msg_brg_dds_sel *)umsg;
                DDS_WRITE(DDS_GPIO, msg->channel);
                mailbox_acknowledge();
                break;
            }
            case MESSAGE_TYPE_BRG_DDS_RESET: {
                unsigned int g;

                g = DDS_READ(DDS_GPIO);
                DDS_WRITE(DDS_GPIO, g | (1 << 7));
                DDS_WRITE(DDS_GPIO, g);

                mailbox_acknowledge();
                break;
            }
            case MESSAGE_TYPE_BRG_DDS_READ_REQUEST: {
                struct msg_brg_dds_read_request *msg;
                struct msg_brg_dds_read_reply rmsg;

                msg = (struct msg_brg_dds_read_request *)umsg;
                rmsg.type = MESSAGE_TYPE_BRG_DDS_READ_REPLY;
                rmsg.data = DDS_READ(msg->address);
                mailbox_send_and_wait(&rmsg);
                break;
            }
            case MESSAGE_TYPE_BRG_DDS_WRITE: {
                struct msg_brg_dds_write *msg;

                msg = (struct msg_brg_dds_write *)umsg;
                DDS_WRITE(msg->address, msg->data);
                mailbox_acknowledge();
                break;
            }
            case MESSAGE_TYPE_BRG_DDS_FUD:
                rtio_fud(rtio_get_counter() + 8000);
                mailbox_acknowledge();
                break;
            default:
                mailbox_acknowledge();
                break;
        }
    }
}
