#include "mailbox.h"
#include "messages.h"
#include "rtio.h"
#include "ttl.h"
#include "dds.h"
#include "bridge.h"

#define TIME_BUFFER (8000 << RTIO_FINE_TS_WIDTH)

static void dds_write(int addr, int data)
{
    rtio_chan_sel_write(RTIO_DDS_CHANNEL);
    rtio_o_address_write(addr);
    rtio_o_data_write(data);
    rtio_o_timestamp_write(rtio_get_counter() + TIME_BUFFER);
    rtio_o_we_write(1);
}

static int dds_read(int addr)
{
    int r;

    dds_write(addr | 128, 0);
    while(rtio_i_status_read() & RTIO_I_STATUS_EMPTY);
    r = rtio_i_data_read();
    rtio_i_re_write(1);
    return r;
}

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
                ttl_set_oe(rtio_get_counter() + TIME_BUFFER, msg->channel, msg->value);
                mailbox_acknowledge();
                break;
            }
            case MESSAGE_TYPE_BRG_TTL_O: {
                struct msg_brg_ttl_out *msg;

                msg = (struct msg_brg_ttl_out *)umsg;
                ttl_set_o(rtio_get_counter() + TIME_BUFFER, msg->channel, msg->value);
                mailbox_acknowledge();
                break;
            }
            case MESSAGE_TYPE_BRG_DDS_INITALL:
                dds_init_all();
                mailbox_acknowledge();
                break;
            case MESSAGE_TYPE_BRG_DDS_SEL: {
                struct msg_brg_dds_sel *msg;

                msg = (struct msg_brg_dds_sel *)umsg;
                dds_write(DDS_GPIO, msg->channel << 1);
                mailbox_acknowledge();
                break;
            }
            case MESSAGE_TYPE_BRG_DDS_RESET: {
                unsigned int g;

                g = dds_read(DDS_GPIO);
                dds_write(DDS_GPIO, g | 1);
                dds_write(DDS_GPIO, g);

                mailbox_acknowledge();
                break;
            }
            case MESSAGE_TYPE_BRG_DDS_READ_REQUEST: {
                struct msg_brg_dds_read_request *msg;
                struct msg_brg_dds_read_reply rmsg;

                msg = (struct msg_brg_dds_read_request *)umsg;
                rmsg.type = MESSAGE_TYPE_BRG_DDS_READ_REPLY;
                rmsg.data = dds_read(msg->address);
                mailbox_send_and_wait(&rmsg);
                break;
            }
            case MESSAGE_TYPE_BRG_DDS_WRITE: {
                struct msg_brg_dds_write *msg;

                msg = (struct msg_brg_dds_write *)umsg;
                dds_write(msg->address, msg->data);
                mailbox_acknowledge();
                break;
            }
            case MESSAGE_TYPE_BRG_DDS_FUD:
                dds_write(DDS_FUD, 0);
                mailbox_acknowledge();
                break;
            default:
                mailbox_acknowledge();
                break;
        }
    }
}
